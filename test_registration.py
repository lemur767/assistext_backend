#!/usr/bin/env python3
"""
Test script to verify registration works after fixing mapper errors
Run this to test the simplified registration endpoint
"""

import requests
import json
import sys

def test_registration_fix():
    """Test the simplified registration endpoint"""
    
    print("🧪 Testing simplified registration endpoint...")
    print("=" * 50)
    
    # Configuration
    BASE_URL = "http://localhost:5000"  # Adjust if needed
    
    # Test data
    test_user = {
        "username": "testuser123",
        "email": "test@example.com",
        "password": "testpassword123",
        "confirm_password": "testpassword123",
        "first_name": "Test",
        "last_name": "User",
        "personal_phone": "+1234567890"
    }
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"⚠️ Health check returned {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        print("   Make sure your Flask app is running!")
        return False
    
    # Test 2: Registration
    print("\n2. Testing user registration...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ Registration successful!")
            data = response.json()
            print(f"   User ID: {data.get('user', {}).get('id')}")
            print(f"   Username: {data.get('user', {}).get('username')}")
            print(f"   Access Token: {'Present' if data.get('access_token') else 'Missing'}")
            return True
        elif response.status_code == 409:
            print("⚠️ User already exists - this is expected on repeated runs")
            return True
        else:
            print(f"❌ Registration failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Raw response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_login():
    """Test login with the registered user"""
    print("\n3. Testing user login...")
    
    BASE_URL = "http://localhost:5000"
    login_data = {
        "username": "testuser123",
        "password": "testpassword123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Login successful!")
            data = response.json()
            print(f"   User: {data.get('user', {}).get('username')}")
            return True
        else:
            print(f"❌ Login failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        return False

def main():
    print("🔧 Testing Registration Fix")
    print("Testing simplified registration without relationship dependencies")
    print()
    
    # Run tests
    registration_works = test_registration_fix()
    login_works = test_login() if registration_works else False
    
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Registration: {'✅ Working' if registration_works else '❌ Failed'}")
    print(f"   Login: {'✅ Working' if login_works else '❌ Failed'}")
    
    if registration_works and login_works:
        print("\n🎉 SUCCESS! Registration is working without mapper errors.")
        print("\n📝 Next steps:")
        print("   1. Add back one model at a time in app/models/__init__.py")
        print("   2. Test after each addition to isolate problematic relationships")
        print("   3. Use lazy='dynamic' or 'select' on problematic relationships")
        print("   4. Consider using back_populates instead of backref")
    else:
        print("\n❌ Registration still has issues. Check:")
        print("   1. Flask app is running on localhost:5000")
        print("   2. Database is connected and accessible")
        print("   3. No syntax errors in the models")
        print("   4. Check Flask console for error messages")
    
    return registration_works and login_works

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
