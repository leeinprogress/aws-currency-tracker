#!/bin/bash

# Example script to login and get an access token
# 
# Prerequisites:
# 1. Replace API_URL with your deployed API Gateway URL
# 2. Replace EMAIL and PASSWORD with your registered user credentials
#
# Usage:
#   export API_URL="https://your-api-id.execute-api.region.amazonaws.com/Prod"
#   export EMAIL="your-email@example.com"
#   export PASSWORD="your-password"
#   ./login.sh

API_URL="${API_URL:-https://your-api-id.execute-api.region.amazonaws.com/Prod}"
EMAIL="${EMAIL:-your-email@example.com}"
PASSWORD="${PASSWORD:-your-password}"

# Login and get access token
curl -X POST "${API_URL}/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${EMAIL}&password=${PASSWORD}"

# Save the access_token from the response to use in other requests
# Example: export ACCESS_TOKEN="your-token-here"

