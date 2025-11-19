# Quick Start Guide

Get the Currency Alert System up and running in a few minutes. This guide walks you through deployment and creating your first alert.

## Prerequisites

Before you start, make sure you have:

1. **AWS Account** with CLI configured
   - Install AWS CLI: https://aws.amazon.com/cli/
   - Configure credentials: `aws configure`

2. **AWS SAM CLI** installed
   - Mac: `brew install aws-sam-cli`
   - Other platforms: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

3. **Telegram Bot Token**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow the instructions
   - Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

4. **Get Your Telegram Chat ID**
   - Start a chat with your bot
   - Send any message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}` in the response
   - Copy that number

5. **KoreaExim API Key** (optional but recommended)
   - Visit: https://www.koreaexim.go.kr/ir/HPHKIR020M01
   - Register and get your authkey
   - Free tier is available

## Deployment Steps

### 1. Build the Application

```bash
sam build
```

This compiles your code and prepares it for deployment.

### 2. Deploy (First Time)

For the first deployment, use guided mode:

```bash
sam deploy --guided
```

When prompted, enter:

- **Stack Name**: `currency-alert-system` (or any name you prefer)
- **AWS Region**: `us-east-1` (or your preferred region)
- **TelegramBotToken**: Your Telegram bot token
- **KoreaEximAuthkey**: Your KoreaExim API authkey (or press Enter to skip)
- **ExchangeApiKey**: Press Enter (legacy, not used)
- **SecretKey**: Press Enter to use default, or generate one:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Confirm changes**: `Y`
- **Allow SAM CLI IAM role creation**: `Y`
- **Disable rollback**: `N` (default)

### 3. Note the API URL

After deployment, you'll see output like:

```
ApiUrl = https://xxxxx.execute-api.region.amazonaws.com/Prod/
```

Save this URL - you'll need it for API calls.

## Create Your First Alert

### Step 1: Register a User

```bash
curl -X POST "YOUR_API_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-secure-password",
    "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID"
  }'
```

### Step 2: Login to Get Access Token

```bash
curl -X POST "YOUR_API_URL/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your-email@example.com&password=your-secure-password"
```

Copy the `access_token` from the response.

### Step 3: Create an Alert

```bash
curl -X POST "YOUR_API_URL/api/v1/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "base_currency": "KRW",
    "target_currency": "USD",
    "target_rate": 1300.0,
    "condition": "below",
    "rate_type": "TTS"
  }'
```

This creates an alert that will notify you when USD/KRW drops below 1300 (TTS rate).

**Note**: `base_currency` must always be "KRW" because the KoreaExim API uses KRW as the base currency.

## How It Works

1. **Every 5 minutes**: The `FetchRatesFunction` Lambda runs
   - Fetches current exchange rates from KoreaExim API
   - Publishes rate update events to EventBridge

2. **EventBridge**: Routes rate update events to `CheckAlertsFunction`

3. **Alert Check**: The function compares current rates with your alerts

4. **Telegram Notification**: If a condition is met, you receive a message on Telegram

## Testing the API

Use the provided test script:

```bash
cd examples
export API_BASE_URL="YOUR_API_URL"
export ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
python test_api.py
```

Or use the shell scripts:

```bash
cd examples
export API_URL="YOUR_API_URL"
export EMAIL="your-email@example.com"
export PASSWORD="your-password"
export ACCESS_TOKEN="your-token"

# Register
./register.sh

# Login
./login.sh

# Create alert
./create_alert.sh
```

## View Your Alerts

```bash
curl "YOUR_API_URL/api/v1/alerts" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Add `?is_active=true` to filter for only active alerts.

## Update an Alert

```bash
curl -X PUT "YOUR_API_URL/api/v1/alerts/{alert_id}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "target_rate": 1350.0,
    "condition": "above"
  }'
```

## Delete an Alert

```bash
curl -X DELETE "YOUR_API_URL/api/v1/alerts/{alert_id}" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Toggle Alert Status

Temporarily disable an alert without deleting it:

```bash
curl -X PUT "YOUR_API_URL/api/v1/alerts/{alert_id}/toggle" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Troubleshooting

### No Telegram Messages?

- Check that your bot token is correct in the SAM template parameters
- Verify your Telegram chat ID is correct
- Make sure you've sent at least one message to your bot
- Check CloudWatch Logs for `CheckAlertsFunction` to see if there are errors

### Rates Not Updating?

- Check CloudWatch Logs for `FetchRatesFunction`
- Verify your KoreaExim API key is correct (if using)
- Check that the scheduled event is enabled in EventBridge

### Alerts Not Triggering?

- Verify your alert conditions are correct
- Check that alerts are active (`is_active: true`)
- Look at CloudWatch Logs for `CheckAlertsFunction` for error messages
- Ensure the rate type (TTS, TTB, DEAL_BAS_R) matches what you're monitoring

### Authentication Errors?

- Make sure you're including the `Authorization: Bearer <token>` header
- Check that your token hasn't expired (default: 30 minutes)
- Verify you're using the correct API URL

### View Logs

```bash
# Fetch rates function logs
sam logs -n FetchRatesFunction --stack-name currency-alert-system --tail

# Check alerts function logs
sam logs -n CheckAlertsFunction --stack-name currency-alert-system --tail

# API logs
sam logs -n CurrencyApi --stack-name currency-alert-system --tail
```

## Cost Estimate

For typical personal use:

- **Free Tier**: Covers most usage
- **Estimated**: ~$0.20-1/month
  - DynamoDB: Pay-per-request, very cheap for low traffic
  - Lambda: 1M free requests/month
  - API Gateway: First 1M requests/month free
  - EventBridge: First 1M custom events/month free

Costs increase with higher traffic, but for personal use, you'll likely stay within free tier limits.

## Next Steps

- Read the [Architecture](ARCHITECTURE.md) document to understand the system design
- Check [Authentication](AUTHENTICATION.md) for security details
- Review [Storage Options](STORAGE_OPTIONS.md) if you need different storage
- Explore the API documentation at `YOUR_API_URL/docs` (Swagger UI)

## Updating the Deployment

After making code changes:

```bash
sam build
sam deploy
```

SAM will detect changes and update only what's necessary.

## Cleanup

To remove all resources and stop incurring costs:

```bash
sam delete --stack-name currency-alert-system
```

This deletes the entire CloudFormation stack, including all resources.
