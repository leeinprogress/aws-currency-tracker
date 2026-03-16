# Product Requirements Document
## KRW Exchange Rate Tracker & Remittance Timing Assistant

**Version:** 1.1
**Status:** Final
**Last Updated:** 2026-03-13
**Author:** Lee Garam

---

## 1. Problem Statement

### The Pain

Korean expats and overseas workers regularly send money back to Korea. The timing of that
transfer can make a meaningful difference — a 1–2% swing in the USD/KRW rate on a $3,000
remittance is $30–60. Over a year of monthly transfers, that adds up.

Yet most people transfer when it's convenient, not when the rate is favorable. They lack
two things:

1. **Awareness** — they don't know whether today's rate is historically good or bad
2. **Alerts** — they have no way to be notified when their target rate is hit

Existing solutions (bank apps, Google Finance) show the current rate but offer no
historical context, no timing guidance, and no alert system.

### Why This Matters Now

The KRW has experienced elevated volatility since 2022. A user who transferred at the
wrong week in 2024 paid 8–10% more than one who waited two weeks. For regular remittance
users, this is a real, recurring financial cost.

---

## 2. Users

### Primary — The Regular Remitter

**Profile:** Korean national living abroad (US, Europe, Japan, Australia). Sends
$1,000–$5,000 home monthly or quarterly. Uses a bank wire or remittance service.

**Current behavior:**
- Checks the rate on Google or a banking app
- Has no reference for whether that rate is good or bad historically
- Transfers when they remember to, not when the rate is optimal
- Has missed favorable windows they didn't know about

**What they need:**
- A simple signal: "Is today a good day to transfer?"
- An alert when the rate hits their personal target
- Enough explanation to trust the signal

### Secondary — The Technical Reviewer

An engineer or hiring manager evaluating this as a portfolio project. They want to see
evidence of production-level thinking: clean architecture, observable systems, security
discipline, and domain understanding beyond CRUD.

---

## 3. Goals

### User Goals

| Goal | Metric | Target |
|---|---|---|
| User can set a rate alert | Alert creation success rate | 100% |
| User receives notification when target rate is hit | Alert delivery rate within 5 min of rate fetch | ≥ 99% |
| User understands whether today's rate is favorable | Scoring endpoint returns valid recommendation | 100% uptime |
| User is not misled on volatile days | Guardrail override on high-vol days | Verified by test suite |

### Product Goals

| Goal | Metric |
|---|---|
| Zero silent alert failures | DLQ message count = 0 in normal operation |
| No secrets exposed | Zero plaintext secrets in codebase or git history |
| Reliable daily rate ingestion | fetch_rates Lambda error rate < 1% |

---

## 4. Solution Overview

A pure serverless backend that does three things:

**1. Rate ingestion**
A scheduled Lambda fetches daily KRW exchange rates (mid, buy, sell) from the Korea Exim
Bank API every morning at 11AM KST and stores them with 90 days of history.

**2. Alert system**
Users register target rates. After each daily fetch, a second Lambda checks all active
alerts against the new rate and sends a Telegram notification when conditions are met.
A dead-letter queue captures any failures — no alert is ever silently dropped.

**3. Timing recommendations**
A scoring engine computes a FAVORABLE / NEUTRAL / WAIT / CAUTION signal for each currency
pair using statistical features (percentile rank, moving averages, volatility, spread).
Hard guardrails override optimistic signals when market conditions are abnormal.

### Why Serverless

The workload is sporadic: one scheduled fetch per day, occasional API calls from users.
Lambda + API Gateway handles this at near-zero cost with no infrastructure to maintain.
An always-on server would be wasteful and harder to justify architecturally.

### Why Telegram

Korean expats already use Telegram widely. The Telegram Bot API is free, works
internationally without SMS fees, and delivers instantly. Email is too easy to miss;
SMS adds cost and setup friction.

---

## 5. User Stories

### Authentication
- As a new user, I want to register with my email and password so I can create a personal account.
- As a returning user, I want to stay logged in without re-entering my password every session.
- As a Google user, I want to sign in with my Google account so I don't need another password.

### Alerts
- As a user, I want to set a target rate for USD/KRW so I'm notified when the rate hits my goal.
- As a user, I want to receive a Telegram message when my target rate is hit so I can act immediately.
- As a user, I want to toggle an alert on or off without deleting it so I can pause it when needed.
- As a user, I want to see my notification history so I know which alerts fired and when.

### Rate Information
- As a user, I want to see the current USD/KRW rate so I know where the market is today.
- As a user, I want to see 90 days of rate history so I can judge whether today is high or low.

### Recommendations
- As a user, I want a simple FAVORABLE / NEUTRAL / WAIT signal so I don't have to interpret charts.
- As a user, I want a short explanation of why the signal is what it is so I can decide whether to trust it.
- As a user, I want the signal to warn me (CAUTION) when market conditions are abnormal so I'm not misled on volatile days.

---

## 6. Functional Requirements

### Must Have

| Area | Requirement |
|---|---|
| Auth | Email/password registration and login with bcrypt password hashing |
| Auth | JWT sessions with short-lived access tokens (15 min) and long-lived refresh tokens (7-day expiry) |
| Auth | Rate limiting on login and registration to prevent abuse |
| Alerts | Create, read, update, delete, and toggle per-user alerts |
| Alerts | Idempotent alert creation — duplicate submissions return the same result |
| Rates | Daily ingestion for USD, EUR, JPY, CNY vs KRW (mid + buy/sell + spread) |
| Rates | 90-day rate history queryable per currency |
| Rates | Statistical snapshot per currency: moving averages, percentile, z-score, volatility, spread ratio |
| Recommendations | Per-currency signal: FAVORABLE / NEUTRAL / WAIT / CAUTION |
| Recommendations | Score breakdown with 2–4 sentence explanation in plain English |
| Recommendations | Guardrails that override optimistic signals on high-volatility or wide-spread days |
| Recommendations | Data quality guards — refuse to score when history is too thin or stale |
| Notifications | Telegram notification within 5 minutes of daily rate fetch |
| Notifications | Notification history queryable by user |
| Notifications | Dead-letter queue captures all failed notification attempts — zero silent drops |
| Notifications | Weekly Telegram summary: 7-day rate movements and alert history |
| Users | View and update profile (Telegram chat ID) |
| Users | Account deletion cascades to all associated data |

### Should Have

| Area | Requirement |
|---|---|
| Auth | Google OAuth as an alternative login method |

### Nice to Have

| Area | Requirement |
|---|---|
| Alerts | Optional user-defined label per alert (e.g. "rent", "savings") |

---

## 7. Non-Functional Requirements

### Reliability

| Requirement | Target |
|---|---|
| Alert delivery after rate fetch | ≥ 99% within 5 minutes |
| API availability | ≥ 99.5% over any 30-day window |
| Failed alert processing | Zero silent drops — all failures land in DLQ |
| Data durability (production) | Point-in-time recovery enabled on all tables |

### Security

| Requirement |
|---|
| Passwords hashed with bcrypt — never stored or logged in plaintext |
| JWT refresh tokens stored as bcrypt hash in database |
| All secrets stored in AWS SSM Parameter Store as SecureString |
| Zero secrets in source code or git history |
| HTTPS enforced — no plaintext HTTP |
| CORS locked to explicit allowed origins in production |
| Input validation on all endpoints |
| Error responses never expose internal details or stack traces |

### Observability

| Requirement |
|---|
| Structured JSON logs for all Lambda functions |
| Alarms on Lambda errors, slow execution, DLQ depth, and API 5xx rate |
| Operational alerts routed to email via SNS |
| Recovery notification when an alarm returns to OK state |

### Cost Awareness

| Decision | Reason |
|---|---|
| DynamoDB PITR disabled in development | Per-table monthly charge; dev data has no recovery value |
| DeletionProtection disabled in development | Allows fast teardown during development |
| Serverless compute | Pay only for actual invocations — zero idle cost |

---

## 8. Out of Scope

| Item | Reason |
|---|---|
| Frontend / web UI | Backend-only; Swagger UI and Postman serve as the interface |
| Additional currency pairs | Korea Exim Bank API supports only the four covered pairs for KRW |
| Real-time rate data | Source API publishes once per business day |
| Fee and commission modeling | Remittance provider fees vary and are not in the rate data |
| Backtest / historical simulation | Separate analytical concern; not part of the alert workflow |
| Multi-currency portfolio tracking | Out of scope for the remittance use case |

---

## 9. Constraints

**Data cadence:** Korea Exim Bank API publishes once per business day. The product is
daily-cadence by design — intraday signals are not possible with this data source.

**Scoring direction:** The engine assumes the user is *receiving* KRW (sending foreign
currency to Korea). A higher USD/KRW rate means more KRW per dollar — favorable.
Users sending KRW abroad have the opposite preference; this case is not handled.
Direction is fixed for this version.

**JPY quoting convention:** JPY rates are quoted per 100 JPY, not per 1 unit.
This is surfaced explicitly in API responses via a `rate_unit` field to prevent
user confusion.

---

## 10. Open Questions

| Question | Decision |
|---|---|
| Scoring explanations in Korean as well as English? | Deferred — English only for now |
| Should users be able to configure remittance direction (receive vs send KRW)? | Deferred — receive-only for this version |
| When Korea Exim Bank API is down, suppress scoring or warn and continue? | Decided: stale > 2 days → include `data_warning` in response, scoring continues |
| Should weekly reports be opt-in per user? | Deferred |