#!/bin/bash

# Example script to register a new user
# 
# Prerequisites:
# 1. Replace API_URL with your deployed API Gateway URL
# 2. Replace EMAIL, PASSWORD, and TELEGRAM_CHAT_ID with your values
#
# Usage:
#   export API_URL="https://your-api-id.execute-api.region.amazonaws.com/Prod"
#   export EMAIL="your-email@example.com"
#   export PASSWORD="your-password"
#   export TELEGRAM_CHAT_ID="your-telegram-chat-id"
#   ./register.sh

API_URL="${API_URL:-https://your-api-id.execute-api.region.amazonaws.com/Prod}"
EMAIL="${EMAIL:-your-email@example.com}"
PASSWORD="${PASSWORD:-your-password}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-your-telegram-chat-id}"

curl -X POST "${API_URL}/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${EMAIL}\",
    \"password\": \"${PASSWORD}\",
    \"telegram_chat_id\": \"${TELEGRAM_CHAT_ID}\"
  }"

