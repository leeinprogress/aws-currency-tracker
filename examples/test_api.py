"""
Simple test script for the Currency Alert API
Run this after deploying to test the endpoints

Prerequisites:
1. Replace API_BASE_URL with your deployed API Gateway URL
2. First, register a user and login to get an access token
3. Replace ACCESS_TOKEN with the token from login response

Usage:
    export API_BASE_URL="https://your-api-id.execute-api.region.amazonaws.com/Prod"
    export ACCESS_TOKEN="your-access-token-here"
    python test_api.py
"""

import requests
import json
import os

# Replace with your API Gateway URL
API_BASE_URL = os.getenv("API_BASE_URL", "https://your-api-id.execute-api.region.amazonaws.com/Prod")

# Replace with your access token (get from /api/v1/auth/login)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "your-access-token-here")

# Headers for authenticated requests
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

def test_create_alert():
    """Test creating an alert"""
    url = f"{API_BASE_URL}/api/v1/alerts"
    # Note: user_id and telegram_chat_id are automatically set from authenticated user
    # base_currency must always be "KRW" (KoreaExim API requirement)
    data = {
        "base_currency": "KRW",
        "target_currency": "USD",
        "target_rate": 1300.0,
        "condition": "below",
        "rate_type": "TTS"  # TTS, TTB, or DEAL_BAS_R
    }
    
    response = requests.post(url, json=data, headers=HEADERS)
    print(f"Create Alert: {response.status_code}")
    if response.status_code != 201:
        print(f"Error: {response.text}")
        return None
    print(json.dumps(response.json(), indent=2))
    return response.json().get('alert_id')

def test_list_alerts():
    """Test listing alerts"""
    url = f"{API_BASE_URL}/api/v1/alerts"
    response = requests.get(url, headers=HEADERS)
    print(f"\nList Alerts: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    print(json.dumps(response.json(), indent=2))

def test_get_alert(alert_id):
    """Test getting a specific alert"""
    url = f"{API_BASE_URL}/api/v1/alerts/{alert_id}"
    response = requests.get(url, headers=HEADERS)
    print(f"\nGet Alert: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    print(json.dumps(response.json(), indent=2))

def test_toggle_alert(alert_id):
    """Test toggling an alert"""
    url = f"{API_BASE_URL}/api/v1/alerts/{alert_id}/toggle"
    response = requests.put(url, headers=HEADERS)
    print(f"\nToggle Alert: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    print(json.dumps(response.json(), indent=2))

def test_update_alert(alert_id):
    """Test updating an alert"""
    url = f"{API_BASE_URL}/api/v1/alerts/{alert_id}"
    data = {
        "target_rate": 1350.0,
        "condition": "above"
    }
    response = requests.put(url, json=data, headers=HEADERS)
    print(f"\nUpdate Alert: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    print(json.dumps(response.json(), indent=2))

def test_delete_alert(alert_id):
    """Test deleting an alert"""
    url = f"{API_BASE_URL}/api/v1/alerts/{alert_id}"
    response = requests.delete(url, headers=HEADERS)
    print(f"\nDelete Alert: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    print("Testing Currency Alert API\n")
    print("=" * 50)
    
    # Create an alert
    alert_id = test_create_alert()
    
    if alert_id:
        # List all alerts
        test_list_alerts()
        
        # Get specific alert
        test_get_alert(alert_id)
        
        # Update alert
        test_update_alert(alert_id)
        
        # Toggle alert
        test_toggle_alert(alert_id)
        
        # Toggle back
        test_toggle_alert(alert_id)
        
        # Delete alert
        # test_delete_alert(alert_id)

