"""
Lambda function to check alerts and send Telegram notifications
Uses storage abstraction to get alerts
"""
import json
import os
import sys
from telegram import Bot

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.repositories import get_alert_repository

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None


async def check_alerts_async(event):
    """
    Checks alerts against current rates and sends Telegram notifications
    Triggered by EventBridge when rates are updated
    """
    # Parse EventBridge event
    if isinstance(event, dict) and 'source' in event and event.get('source') == 'currency.tracker':
        if isinstance(event.get('detail'), str):
            rate_data = json.loads(event['detail'])
        else:
            rate_data = event.get('detail', {})
        
        base_currency = rate_data.get('base_currency')
        rates = rate_data.get('rates', {})
        timestamp = rate_data.get('timestamp', '')
    elif isinstance(event, dict) and 'detail' in event:
        if isinstance(event['detail'], str):
            rate_data = json.loads(event['detail'])
        else:
            rate_data = event.get('detail', {})
        
        base_currency = rate_data.get('base_currency')
        rates = rate_data.get('rates', {})
        timestamp = rate_data.get('timestamp', '')
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid event format', 'received': str(event)[:200]})
        }
    
    if not base_currency or not rates:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing base_currency or rates in event'})
        }
    
    # Get storage and fetch active alerts for this base currency
    repository = get_alert_repository()
    alerts = await repository.get_active_alerts_by_base_currency(base_currency)
    
    triggered_alerts = []
    
    for alert in alerts:
        target_currency = alert.target_currency.upper()
        target_rate = alert.target_rate
        condition = alert.condition.lower()
        rate_type = alert.rate_type.upper()  # TTS, TTB, or DEAL_BAS_R
        telegram_chat_id = alert.telegram_chat_id
        
        # Get current rate for target currency
        currency_data = rates.get(target_currency)
        
        if currency_data is None:
            print(f"Currency {target_currency} not found in rates")
            continue
        
        # KoreaExim API response format: {currency_code: {TTS, TTB, DEAL_BAS_R, ...}}
        if isinstance(currency_data, dict):
            # Select rate based on rate_type
            current_rate = currency_data.get(rate_type)
            if current_rate is None:
                print(f"Rate type {rate_type} not found for currency {target_currency}")
                continue
            current_rate = float(current_rate)
            cur_nm = currency_data.get('cur_nm', target_currency)
        else:
            # Legacy format compatibility (simple number)
            current_rate = float(currency_data)
            cur_nm = target_currency
        
        should_alert = False
        
        # Check condition
        if condition == 'above' and current_rate >= target_rate:
            should_alert = True
        elif condition == 'below' and current_rate <= target_rate:
            should_alert = True
        
        if should_alert:
            # Send Telegram notification
            message = (
                f"🔔 Currency Alert Triggered!\n\n"
                f"📊 {alert.base_currency}/{alert.target_currency} ({cur_nm})\n"
                f"🎯 Target: {target_rate} ({condition})\n"
                f"💰 Current Rate ({rate_type}): {current_rate}\n"
                f"⏰ {timestamp}"
            )
            
            try:
                if bot:
                    bot.send_message(
                        chat_id=telegram_chat_id,
                        text=message
                    )
                    triggered_alerts.append(alert.alert_id)
                else:
                    print(f"Telegram bot not configured. Would send: {message}")
            except Exception as e:
                print(f"Error sending Telegram message: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Checked {len(alerts)} alerts',
            'triggered': len(triggered_alerts),
            'alert_ids': triggered_alerts
        })
    }


def lambda_handler(event, context):
    """Lambda handler"""
    try:
        import asyncio
        return asyncio.run(check_alerts_async(event))
    except Exception as e:
        print(f"Error in check_alerts: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
