"""
Lambda function to check alerts and send Telegram notifications
Uses storage abstraction to get alerts
"""
import json
import os
import sys
from telegram import Bot
from telegram.request import HTTPXRequest

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.repositories import get_alert_repository

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

def get_telegram_bot():
    """Create a new Telegram bot instance for each use"""
    if not TELEGRAM_BOT_TOKEN:
        return None
    # Use HTTPXRequest with connection pool settings for Lambda
    request = HTTPXRequest(
        connection_pool_size=1,
        read_timeout=5.0,
        write_timeout=5.0,
        connect_timeout=5.0,
        pool_timeout=5.0
    )
    return Bot(token=TELEGRAM_BOT_TOKEN, request=request)


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
    
    print(f"Found {len(alerts)} active alerts for base currency {base_currency}")
    print(f"Rates available for currencies: {list(rates.keys())[:10]}...")  # Log first 10 currencies
    
    triggered_alerts = []
    
    for alert in alerts:
        target_currency = alert.target_currency.upper()
        target_rate = alert.target_rate
        condition = alert.condition.lower()
        rate_type = alert.rate_type.upper()  # TTS, TTB, or DEAL_BAS_R
        telegram_chat_id = alert.telegram_chat_id
        
        print(f"Processing alert: {alert.alert_id}")
        print(f"  Target currency: {target_currency}, Target rate: {target_rate}, Condition: {condition}, Rate type: {rate_type}")
        
        # Get current rate for target currency
        currency_data = rates.get(target_currency)
        
        if currency_data is None:
            print(f"Currency {target_currency} not found in rates. Available currencies: {list(rates.keys())}")
            continue
        
        print(f"  Found currency data for {target_currency}: {currency_data}")
        
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
        
        print(f"  Current rate ({rate_type}): {current_rate}, Target: {target_rate}, Condition: {condition}")
        
        # Check condition
        if condition == 'above' and current_rate >= target_rate:
            should_alert = True
            print(f"  ✅ Condition met: {current_rate} >= {target_rate}")
        elif condition == 'below' and current_rate <= target_rate:
            should_alert = True
            print(f"  ✅ Condition met: {current_rate} <= {target_rate}")
        else:
            print(f"  ❌ Condition not met: {current_rate} {condition} {target_rate}")
        
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
                bot = get_telegram_bot()
                if bot:
                    # Use async method for sending messages
                    await bot.send_message(
                        chat_id=telegram_chat_id,
                        text=message
                    )
                    # Close the bot connection properly
                    await bot.close()
                    triggered_alerts.append(alert.alert_id)
                    print(f"Successfully sent alert to chat {telegram_chat_id} for alert {alert.alert_id}")
                else:
                    print(f"Telegram bot not configured. Would send: {message}")
            except Exception as e:
                print(f"Error sending Telegram message to chat {telegram_chat_id}: {str(e)}")
                # Try to close bot if it exists
                try:
                    bot = get_telegram_bot()
                    if bot:
                        await bot.close()
                except Exception:
                    pass
                # Don't fail the entire function if one message fails
    
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
