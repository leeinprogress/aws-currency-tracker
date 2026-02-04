#!/bin/bash

# Example script to create a currency alert
# 
# Prerequisites:
# 1. Replace API_URL with your deployed API Gateway URL
# 2. First, login to get an access token (see login.sh example)
# 3. Replace ACCESS_TOKEN with the token from login response
#
# Usage:
#   export API_URL="https://your-api-id.execute-api.region.amazonaws.com/Prod"
#   export ACCESS_TOKEN="your-access-token-here"
#   ./create_alert.sh

API_URL="${API_URL:-https://your-api-id.execute-api.region.amazonaws.com/Prod}"
ACCESS_TOKEN="${ACCESS_TOKEN:-your-access-token-here}"

curl -X POST "${API_URL}/api/v1/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{
    "base_currency": "KRW",
    "target_currency": "USD",
    "target_rate": 1300.0,
    "condition": "below",
    "rate_type": "TTS"
  }'

