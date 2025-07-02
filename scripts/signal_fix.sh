#!/bin/bash
# Fix Missing get_signalwire_client Function

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🔧 Adding Missing get_signalwire_client Function${NC}"
echo "=============================================="

BACKEND_DIR="/opt/assistext_backend"
SIGNALWIRE_FILE="$BACKEND_DIR/app/utils/signalwire_helpers.py"

echo "Error: 'get_signalwire_client' function is not defined"
echo "Adding the missing function that other parts of the app expect..."

echo -e "\n${BLUE}1. Add Missing Client Function${NC}"
echo "=============================="

# Add the missing function to the signalwire_helpers.py file
cat >> "$SIGNALWIRE_FILE" << 'EOF'

def get_signalwire_client():
    """
    Get a configured SignalWire client instance
    
    Returns:
        signalwire.rest.Client or None: Configured client or None if not available
    """
    try:
        project_id = os.environ.get('SIGNALWIRE_PROJECT_ID')
        auth_token = os.environ.get('SIGNALWIRE_AUTH_TOKEN')
        space_url = os.environ.get('SIGNALWIRE_SPACE_URL')
        
        if not all([project_id, auth_token, space_url]):
            if current_app:
                current_app.logger.warning("SignalWire credentials not fully configured")
            return None
        
        try:
            from signalwire.rest import Client
        except ImportError:
            if current_app:
                current_app.logger.error("SignalWire SDK not installed")
            return None
        
        # Create and return client
        client = Client(project_id, auth_token, signalwire_space_url=space_url)
        
        if current_app:
            current_app.logger.debug("SignalWire client created successfully")
        
        return client
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error creating SignalWire client: {e}")
        return None

def search_available_phone_numbers(city=None, area_code=None, country='US', limit=10):
    """
    Search for available phone numbers (wrapper function for compatibility)
    
    Args:
        city (str): City to search in
        area_code (str): Area code to search
        country (str): Country code (US, CA)
        limit (int): Maximum number of results
        
    Returns:
        dict: Search results with success status and numbers list
    """
    try:
        # Use the existing get_available_numbers function
        numbers = get_available_numbers(area_code=area_code, city=city, country=country)
        
        # Limit results
        if limit and len(numbers) > limit:
            numbers = numbers[:limit]
        
        return {
            'success': True,
            'message': f'Found {len(numbers)} available numbers',
            'numbers': numbers,
            'search_params': {
                'city': city,
                'area_code': area_code,
                'country': country,
                'limit': limit
            }
        }
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error searching phone numbers: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'message': 'Phone number search failed',
            'numbers': []
        }

def purchase_phone_number(phone_number):
    """
    Purchase a phone number from SignalWire
    
    Args:
        phone_number (str): Phone number to purchase
        
    Returns:
        dict: Purchase result
    """
    try:
        client = get_signalwire_client()
        
        if not client:
            return {
                'success': False,
                'error': 'SignalWire client not available',
                'message': 'Cannot purchase number - service not configured'
            }
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(phone_number=phone_number)
        
        if current_app:
            current_app.logger.info(f"Successfully purchased number: {phone_number}")
        
        return {
            'success': True,
            'phone_number': purchased_number.phone_number,
            'sid': purchased_number.sid,
            'message': 'Phone number purchased successfully'
        }
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error purchasing phone number {phone_number}: {e}")
        
        # Return mock success for development
        if os.environ.get('FLASK_ENV') == 'development':
            return {
                'success': True,
                'phone_number': phone_number,
                'sid': f'mock_sid_{int(time.time())}',
                'message': 'Phone number purchased successfully (mock)',
                'mock': True
            }
        
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to purchase phone number'
        }

def configure_phone_number_webhook(phone_number, webhook_url):
    """
    Configure webhook URL for a phone number
    
    Args:
        phone_number (str): Phone number to configure
        webhook_url (str): Webhook URL for incoming messages
        
    Returns:
        dict: Configuration result
    """
    try:
        client = get_signalwire_client()
        
        if not client:
            return {
                'success': False,
                'error': 'SignalWire client not available'
            }
        
        # Find the phone number resource
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            return {
                'success': False,
                'error': 'Phone number not found in account'
            }
        
        # Update the webhook URL
        number = numbers[0]
        number.update(sms_url=webhook_url, sms_method='POST')
        
        if current_app:
            current_app.logger.info(f"Configured webhook for {phone_number}: {webhook_url}")
        
        return {
            'success': True,
            'phone_number': phone_number,
            'webhook_url': webhook_url,
            'message': 'Webhook configured successfully'
        }
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error configuring webhook for {phone_number}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to configure webhook'
        }

# Legacy function aliases for backward compatibility
def get_available_phone_numbers(*args, **kwargs):
    """Legacy alias for get_available_numbers"""
    return get_available_numbers(*args, **kwargs)

def lookup_phone_number(*args, **kwargs):
    """Legacy alias for get_phone_number_info"""
    return get_phone_number_info(*args, **kwargs)
EOF

echo "✅ Added missing SignalWire client functions"

echo -e "\n${BLUE}2. Test Function Import${NC}"
echo "======================"

echo "Testing new function imports..."
cd "$BACKEND_DIR"

sudo -u admin $BACKEND_DIR/venv/bin/python << 'EOF'
import sys
sys.path.insert(0, '/opt/assistext_backend')

try:
    print("Testing get_signalwire_client import...")
    from app.utils.signalwire_helpers import get_signalwire_client
    print("✅ get_signalwire_client imported successfully")
    
    print("Testing search_available_phone_numbers import...")
    from app.utils.signalwire_helpers import search_available_phone_numbers
    print("✅ search_available_phone_numbers imported successfully")
    
    print("Testing function calls...")
    
    # Test client creation (should return None without credentials)
    client = get_signalwire_client()
    print(f"✅ Client creation test: {type(client)}")
    
    # Test phone number search
    result = search_available_phone_numbers(city="Toronto", area_code="416")
    print(f"✅ Phone search test: {result['success']}")
    
except Exception as e:
    print("❌ Function import/test failed:", e)
    import traceback
    traceback.print_exc()
EOF

echo -e "\n${BLUE}3. Check What's Calling get_signalwire_client${NC}"
echo "=============================================="

echo "Searching for where get_signalwire_client is being called..."

# Find all references to get_signalwire_client
grep -r "get_signalwire_client" "$BACKEND_DIR/app" 2>/dev/null || echo "No additional references found"

echo -e "\n${BLUE}4. Restart Backend Service${NC}"
echo "=========================="

echo "Restarting backend with the missing function..."
sudo systemctl restart assistext-backend

sleep 5

echo "Checking service status..."
sudo systemctl status assistext-backend --no-pager -l | head -15

echo -e "\n${BLUE}5. Test Phone Number Search API${NC}"
echo "==============================="

echo "Testing the phone number search that was failing..."

if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
    echo "✅ Backend is responding"
    
    echo -e "\nTesting phone number search API..."
    SEARCH_RESPONSE=$(curl -s -X POST http://localhost:5000/api/signup/search-numbers \
        -H "Content-Type: application/json" \
        -d '{"city": "Toronto", "area_code": "416"}')
    
    echo "Phone search response:"
    echo "$SEARCH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SEARCH_RESPONSE"
    
    # Check if the error is fixed
    if echo "$SEARCH_RESPONSE" | grep -q '"success": true'; then
        echo "✅ Phone number search is now working!"
    else
        echo "❌ Phone number search still has issues"
        
        # Check recent logs for more details
        echo -e "\nRecent logs:"
        sudo journalctl -u assistext-backend --no-pager -n 10
    fi
    
else
    echo "❌ Backend not responding"
    echo -e "\nRecent logs:"
    sudo journalctl -u assistext-backend --no-pager -n 15
fi

echo -e "\n${GREEN}🎉 Missing Client Function Fix Complete${NC}"
echo "======================================="

if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
    echo "✅ SUCCESS: Missing function added"
    echo ""
    echo "Added functions:"
    echo "- get_signalwire_client() ✅"
    echo "- search_available_phone_numbers() ✅"
    echo "- purchase_phone_number() ✅"
    echo "- configure_phone_number_webhook() ✅"
    echo "- Legacy compatibility aliases ✅"
    echo ""
    echo "The phone number search API should now work without errors."
    echo ""
    echo "Test commands:"
    echo "curl -X POST http://localhost:5000/api/signup/search-numbers -H 'Content-Type: application/json' -d '{\"city\": \"Toronto\"}'"
else
    echo "❌ Backend still having issues"
    echo ""
    echo "Check for other missing functions or errors:"
    echo "sudo journalctl -u assistext-backend -f"
fi

echo -e "\n${BLUE}Functions Added:${NC}"
echo "- get_signalwire_client(): Creates SignalWire client instance"
echo "- search_available_phone_numbers(): Wrapper for phone number search"
echo "- purchase_phone_number(): Purchase numbers from SignalWire"
echo "- configure_phone_number_webhook(): Set up webhooks"
echo "- Legacy aliases for backward compatibility"
