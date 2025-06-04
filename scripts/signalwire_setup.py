#!/usr/bin/env python3
"""
SignalWire Setup Script for SMS AI Responder
Configures phone numbers and webhooks
"""

import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.signalwire_helpers import get_signalwire_client


def list_phone_numbers():
    """List all SignalWire phone numbers"""
    try:
        client = get_signalwire_client()
        numbers = client.incoming_phone_numbers.list()
        
        print("📞 Your SignalWire Phone Numbers:")
        print("=" * 50)
        
        for number in numbers:
            print(f"Number: {number.phone_number}")
            print(f"  SID: {number.sid}")
            print(f"  Name: {number.friendly_name}")
            print(f"  SMS URL: {number.sms_url}")
            print(f"  Voice URL: {number.voice_url}")
            print(f"  Capabilities: {number.capabilities}")
            print("-" * 30)
        
        return numbers
        
    except Exception as e:
        print(f"❌ Error listing phone numbers: {e}")
        return []


def configure_webhook(phone_number_sid, webhook_url):
    """Configure webhook for a phone number"""
    try:
        client = get_signalwire_client()
        
        number = client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        print(f"✅ Webhook configured for {number.phone_number}")
        print(f"   Webhook URL: {webhook_url}")
        return True
        
    except Exception as e:
        print(f"❌ Error configuring webhook: {e}")
        return False


def setup_webhooks():
    """Interactive webhook setup"""
    print("🔗 SignalWire Webhook Configuration")
    print("=" * 50)
    
    # Get webhook base URL
    webhook_base = input("Enter your webhook base URL (e.g., https://your-domain.com): ").strip()
    if not webhook_base:
        print("❌ Webhook URL is required")
        return
    
    webhook_url = f"{webhook_base}/api/webhooks/sms"
    print(f"Webhook URL will be: {webhook_url}")
    
    # List phone numbers
    numbers = list_phone_numbers()
    if not numbers:
        return
    
    print("\nWhich phone numbers would you like to configure?")
    
    for i, number in enumerate(numbers):
        print(f"{i + 1}. {number.phone_number} ({number.friendly_name})")
    
    try:
        selection = input("\nEnter number(s) (comma-separated, or 'all'): ").strip()
        
        if selection.lower() == 'all':
            selected_numbers = numbers
        else:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_numbers = [numbers[i] for i in indices if 0 <= i < len(numbers)]
        
        # Configure webhooks
        for number in selected_numbers:
            configure_webhook(number.sid, webhook_url)
        
        print(f"\n✅ Configured webhooks for {len(selected_numbers)} phone numbers")
        
    except (ValueError, IndexError) as e:
        print(f"❌ Invalid selection: {e}")


def test_webhook(phone_number):
    """Test webhook configuration"""
    print(f"🧪 Testing webhook for {phone_number}")
    
    # Simulate webhook call
    webhook_url = "http://localhost:5000/api/webhooks/test"
    test_data = {
        "message": "Test message from SignalWire setup",
        "from": "+1234567890",
        "to": phone_number
    }
    
    try:
        response = requests.post(webhook_url, json=test_data, timeout=10)
        if response.status_code == 200:
            print("✅ Webhook test successful")
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Webhook test error: {e}")
        return False


def main():
    """Main setup function"""
    print("🚀 SignalWire Setup for SMS AI Responder")
    print("=" * 50)
    
    # Check credentials
    required_env = ['SIGNALWIRE_PROJECT_ID', 'SIGNALWIRE_AUTH_TOKEN', 'SIGNALWIRE_SPACE_URL']
    missing = [env for env in required_env if not os.environ.get(env)]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these variables and try again.")
        sys.exit(1)
    
    while True:
        print("\nWhat would you like to do?")
        print("1. List phone numbers")
        print("2. Configure webhooks")
        print("3. Test webhook")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            list_phone_numbers()
        elif choice == '2':
            setup_webhooks()
        elif choice == '3':
            phone_number = input("Enter phone number to test: ").strip()
            test_webhook(phone_number)
        elif choice == '4':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == '__main__':
    main()