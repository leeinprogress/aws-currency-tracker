"""
Lambda function to fetch currency rates from KoreaExim API
Uses storage abstraction to get active alerts
"""
import json
import os
import sys
from datetime import datetime
import boto3

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.repositories import get_alert_repository
from app.clients.exchange_rate_client import KoreaEximExchangeRateClient

# Environment variables
KOREAEXIM_AUTHKEY = os.environ.get('KOREAEXIM_AUTHKEY', '')
EVENTBRIDGE_BUS = os.environ.get('EVENTBRIDGE_BUS', 'currency-events')

eventbridge = boto3.client('events')


async def fetch_rates_async():
    """Async function to fetch rates from KoreaExim API"""
    repository = get_alert_repository()
    
    # Get all active alerts
    alerts = await repository.list_alerts(is_active=True)
    
    if not alerts:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'No active alerts to process'})
        }
    
    try:
        # Initialize KoreaExim API client
        client = KoreaEximExchangeRateClient(authkey=KOREAEXIM_AUTHKEY)
        
        # Fetch rates for today
        today = datetime.now().strftime("%Y%m%d")
        exchange_rates = client.fetch_rates(searchdate=today, data="AP01")
        
        if not exchange_rates:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No exchange rates available'})
            }
        
        # Convert exchange rate data to dictionary (store TTS, TTB, DEAL_BAS_R by currency code)
        rates_by_currency = {}
        for rate in exchange_rates:
            currency_code = rate.cur_unit.upper()
            rates_by_currency[currency_code] = {
                'cur_unit': rate.cur_unit,
                'cur_nm': rate.cur_nm,
                'TTS': rate.tts,
                'TTB': rate.ttb,
                'DEAL_BAS_R': rate.deal_bas_r
            }
        
        # KoreaExim API uses KRW as base, so base_currency is always KRW
        base_currency = "KRW"
        
        # Publish rate update event to EventBridge
        eventbridge.put_events(
            Entries=[{
                'Source': 'currency.tracker',
                'DetailType': 'Rate Updated',
                'Detail': json.dumps({
                    'base_currency': base_currency,
                    'rates': rates_by_currency,  # {currency_code: {TTS, TTB, DEAL_BAS_R, ...}}
                    'timestamp': datetime.utcnow().isoformat()
                }),
                'EventBusName': EVENTBRIDGE_BUS
            }]
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Fetched rates for {len(rates_by_currency)} currencies',
                'currencies': list(rates_by_currency.keys()),
                'base_currency': base_currency
            })
        }
        
    except Exception as e:
        print(f"Error fetching rates: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to fetch rates: {str(e)}'})
        }


def lambda_handler(event, context):
    """
    Fetches currency rates and publishes to EventBridge
    """
    try:
        import asyncio
        return asyncio.run(fetch_rates_async())
    except Exception as e:
        print(f"Error in fetch_rates: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
