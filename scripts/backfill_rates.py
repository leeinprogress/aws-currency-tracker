#!/usr/bin/env python3
"""One-time backfill script: populate rate-history table with the last N days of data.

Usage:
    python scripts/backfill_rates.py [--days 90] [--dry-run]

Required env vars:
    KOREAEXIM_AUTHKEY       — Korea Exim Bank API key
    RATE_HISTORY_TABLE_NAME — DynamoDB table name (default: rate-history)
    AWS_REGION              — AWS region (default: ap-northeast-2)

AWS credentials must be configured (via ~/.aws/credentials, env vars, or IAM role).

Why this exists:
    compute_features() requires at least 7 days of rate history. Without this script,
    the recommendations endpoint is unavailable for the first 7 trading days after
    initial deployment (cold start problem).

Idempotency:
    Safe to run multiple times. DynamoDB put_item overwrites on the same PK/SK,
    so re-running produces identical records with no side effects.

Timestamp note:
    Each record's timestamp is set to 11:00 UTC on the source date (not datetime.now()).
    The rate-history table uses timestamp as the sort key, and find_by_currency_range()
    queries against it. Using now() would bunch all 90 records at the same timestamp,
    making every range query return all records and producing nonsensical MAs.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add src/ to sys.path so app.* imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from app.clients.exchange_rate_client import (  # noqa: E402
    KoreaEximExchangeRateClient,
    NoDataAvailableError,
    RateLimitExceededError,
)
from app.domain.entities.rate_history import RateHistory  # noqa: E402
from app.infrastructure.logging.logger import get_logger, setup_logging  # noqa: E402
from app.infrastructure.persistence.dynamodb_rate_history_repository import (  # noqa: E402
    DynamoDBRateHistoryRepository,
)

setup_logging(level="INFO")
logger = get_logger(__name__)


async def backfill(days: int, dry_run: bool) -> None:
    client = KoreaEximExchangeRateClient()
    repo = DynamoDBRateHistoryRepository()

    today = datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)  # used as created_at for TTL calculation

    saved_total = 0
    skipped_dates = 0

    for offset in range(1, days + 1):
        target_date = today - timedelta(days=offset)
        searchdate = target_date.strftime("%Y%m%d")

        # Set timestamp to 11:00 UTC on the source date.
        # Korea Exim Bank publishes rates around 11am KST (02:00 UTC).
        # We use 11:00 UTC (8pm KST) as a safe post-publication marker.
        historical_ts = datetime(
            target_date.year, target_date.month, target_date.day,
            11, 0, 0, tzinfo=timezone.utc,
        )

        try:
            rates = client.fetch_rates(searchdate=searchdate)
        except NoDataAvailableError:
            logger.info("skipping_no_data", date=searchdate, reason="weekend_or_holiday")
            skipped_dates += 1
            continue
        except RateLimitExceededError:
            logger.warning("rate_limit_hit", date=searchdate, saved_so_far=saved_total)
            print(
                f"⚠  Rate limit hit at {searchdate}. "
                f"Backfilled {saved_total} records before stopping. "
                "Re-run tomorrow to continue."
            )
            return

        records = [
            RateHistory(
                currency_code=r.cur_unit.upper(),
                timestamp=historical_ts,   # ← historical date, NOT datetime.now()
                currency_name=r.cur_nm,
                ttb=r.ttb,
                tts=r.tts,
                deal_bas_r=r.deal_bas_r,
                source_date=searchdate,
                created_at=now,
                buy_rate=r.ttb,
                sell_rate=r.tts,
                spread=r.tts - r.ttb,
            )
            for r in rates
        ]

        if dry_run:
            logger.info("dry_run_would_save", date=searchdate, records=len(records))
        else:
            count = await repo.save_batch(records)
            saved_total += count
            logger.info("saved", date=searchdate, records=count)

    trading_days = days - skipped_dates
    action = "Would write" if dry_run else "Wrote"
    print(
        f"✓  {action} records for {trading_days} trading days "
        f"({skipped_dates} date(s) skipped — weekends/holidays)."
    )
    if not dry_run:
        print(f"   Total records written: {saved_total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill rate-history table with the last N calendar days of exchange rate data."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of calendar days to look back (default: 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without touching DynamoDB",
    )
    args = parser.parse_args()

    if args.dry_run:
        print(f"DRY RUN — scanning last {args.days} calendar days. No DynamoDB writes.")
    else:
        print(f"Backfilling last {args.days} calendar days into rate-history table...")

    asyncio.run(backfill(args.days, args.dry_run))


if __name__ == "__main__":
    main()
