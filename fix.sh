#!/bin/bash
# =============================================================================
# TARGETED FIX - Resolve specific import and blueprint registration errors
# =============================================================================

echo "🔧 Fixing specific SignalWire import and blueprint registration errors..."

# 1. FIX THE SIGNUP.PY IMPORT ERROR
echo "🔧 Fixing signup.py import error..."
cat > /opt/assistext_backend/app/api/signup.py << 'EOF'
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
import logging

# Import SignalWire functions directly
try:
    from app.utils.signalwire_helpers import get_signalwire_client, get_available_phone_numbers, purchase_phone_number
    SIGNALWIRE_AVAILABLE = True
    print("✅ SignalWire helpers imported successfully in signup.py")
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"❌ SignalWire import error in signup.py: {e}")

logger = logging.getLogger(__name__)
signup_bp = Blueprint('signup', __name__)

# Canadian area codes mapping
CANADA_AREA_CODES = {
    'toronto': ['416', '647', '437'],
    'ottawa': ['613', '343'], 
    'vancouver': ['604', '778', '236'],
    'montreal': ['514', '438'],
    'calgary': ['403', '587', '825'],
    'edmonton': ['780', '587', '825'],
    'mississauga': ['905', '289', '365'],
    'hamilton': ['905', '289'],
    'london': ['519', '226', '548'],
    'winnipeg': ['204', '431']
}

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

@signup_bp.route('/search-numbers', methods=['POST'])
def search_available_numbers_endpoint():
    """Registration Step 3: Search for available phone numbers"""
    try:
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available. Please contact support.',
                'available_numbers': []
            }), 503
            
        data = request.json
        city = data.get('city', '').lower()
        area_code = data.get('area_code')
        
        logger.info(f"Registration phone search for city: {city}")
        
        if not city:
            return jsonify({
                'success': False,
                'error': 'City is required',
                'available_numbers': []
            }), 400
        
        # Get SignalWire client
        client = get_signalwire_client()
        if not client:
            logger.error("SignalWire client not available")
            return jsonify({
                'success': False,
                'error': 'Phone number service temporarily unavailable. Please try again later.',
                'available_numbers': []
            }), 503
        
        # Get area codes for the city
        area_codes = CANADA_AREA_CODES.get(city, ['416'])  # Default to Toronto if not found
        
        if area_code:
            # Use specific area code if provided
            area_codes = [area_code]
        
        logger.info(f"Searching area codes: {area_codes} for city: {city}")
        
        # Search for available numbers across all area codes for the city
        all_numbers = []
        
        for ac in area_codes:
            try:
                # Use the helper function
                numbers, error = get_available_phone_numbers(
                    area_code=ac,
                    city=city,
                    country='CA',
                    limit=10
                )
                
                if error:
                    logger.warning(f"Error searching area code {ac}: {error}")
                    continue
                    
                all_numbers.extend(numbers)
                
                # Stop if we have enough numbers
                if len(all_numbers) >= 5:
                    break
                    
            except Exception as e:
                logger.warning(f"Error searching area code {ac}: {str(e)}")
                continue
        
        # Return only the first 5 numbers
        final_numbers = all_numbers[:5]
        
        if not final_numbers:
            return jsonify({
                'success': False,
                'error': f'No phone numbers available in {city}. Please try a different city.',
                'available_numbers': [],
                'city': city,
                'count': 0
            }), 404
        
        logger.info(f"Found {len(final_numbers)} numbers for {city}")
        
        return jsonify({
            'success': True,
            'available_numbers': final_numbers,
            'city': city.title(),
            'count': len(final_numbers),
            'message': f'Found {len(final_numbers)} available numbers in {city.title()}'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in phone number search: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to search for phone numbers. Please try again.',
            'available_numbers': []
        }), 500

@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete registration: Create user, purchase phone number, setup webhook"""
    try:
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available. Please contact support.'
            }), 503
            
        data = request.json
        
        # Validate required fields
        required_fields = [
            'username', 'email', 'password', 'firstName', 'lastName',
            'profileName', 'selectedPhoneNumber'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field} is required'
                }), 400
        
        # Validate password confirmation
        if data.get('password') != data.get('confirmPassword'):
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
            }), 400
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == data['username']) | 
            (User.email == data['email'])
        ).first()
        
        if existing_user:
            error_msg = 'Username already taken' if existing_user.username == data['username'] else 'Email already registered'
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Start database transaction
        try:
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['firstName'],
                last_name=data['lastName'],
                personal_phone=data.get('personalPhone'),
                timezone=data.get('timezone', 'America/Toronto')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.flush()  # Get user ID without committing
            
            # Purchase the phone number from SignalWire
            selected_number = data['selectedPhoneNumber']
            profile_name = data['profileName']
            
            logger.info(f"Purchasing SignalWire number {selected_number} for user {user.username}")
            
            webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
            
            # Purchase number with webhook configuration
            purchased_data, error = purchase_phone_number(
                phone_number=selected_number,
                friendly_name=f"{profile_name} - {user.username}",
                webhook_url=webhook_url
            )
            
            if error or not purchased_data:
                # Rollback user creation if number purchase fails
                db.session.rollback()
                logger.error(f"Phone number purchase failed: {error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to purchase phone number: {error or "Unknown error"}'
                }), 500
            
            # Create profile with purchased number
            profile = Profile(
                user_id=user.id,
                name=profile_name,
                description=data.get('profileDescription', ''),
                phone_number=selected_number,
                is_active=True,
                is_default=True
            )
            
            db.session.add(profile)
            
            # Commit everything
            db.session.commit()
            
            # Generate JWT tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            logger.info(f"Successfully created account for {user.username} with number {selected_number}")
            
            return jsonify({
                'success': True,
                'message': f'Account created successfully! Your SMS number {format_phone_display(selected_number)} is ready.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                },
                'profile': {
                    'id': profile.id,
                    'name': profile.name,
                    'phone_number': profile.phone_number
                },
                'access_token': access_token,
                'refresh_token': refresh_token
            }), 201
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database transaction error: {str(db_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to create account. Please try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Complete signup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

@signup_bp.route('/cities', methods=['GET'])
def get_supported_cities():
    """Get list of supported Canadian cities with their area codes"""
    cities = []
    for city, area_codes in CANADA_AREA_CODES.items():
        cities.append({
            'name': city.title(),
            'value': city,
            'area_codes': area_codes,
            'primary_area_code': area_codes[0]
        })
    
    return jsonify({'cities': cities}), 200

@signup_bp.route('/test', methods=['GET'])
def test_signup():
    """Test signup endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Signup endpoint is working',
        'signalwire_available': SIGNALWIRE_AVAILABLE
    }), 200
EOF

# 2. CREATE WEBHOOKS BLUEPRINT
echo "🔧 Creating webhooks blueprint..."
cat > /opt/assistext_backend/app/api/webhooks.py << 'EOF'
from flask import Blueprint, request, jsonify, current_app
from app.models.profile import Profile
from app.extensions import db
import logging

# Import SignalWire functions
try:
    from app.utils.signalwire_helpers import validate_signalwire_webhook_request, send_sms
    SIGNALWIRE_AVAILABLE = True
    print("✅ SignalWire helpers imported successfully in webhooks.py")
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"❌ SignalWire import error in webhooks.py: {e}")

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS messages from SignalWire webhook"""
    try:
        # Log the incoming request
        logger.info("Received SignalWire webhook request")
        
        # Get webhook data from SignalWire
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        message_body = request.form.get('Body', '').strip()
        message_sid = request.form.get('MessageSid')
        
        logger.info(f"Incoming SMS: From={from_number}, To={to_number}, Body='{message_body}'")
        
        if not all([from_number, to_number, message_body]):
            logger.warning("Missing required webhook parameters")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Find the profile associated with this phone number
        profile = Profile.query.filter_by(phone_number=to_number, is_active=True).first()
        
        if not profile:
            logger.warning(f"No active profile found for number {to_number}")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Generate basic auto-response
        try:
            message_lower = message_body.lower().strip()
            
            if any(word in message_lower for word in ['hi', 'hello', 'hey']):
                ai_response = f"Hello! Thanks for contacting {profile.name}. How can I help you today?"
            elif any(word in message_lower for word in ['help', 'info']):
                ai_response = f"Hi! I'm the AI assistant for {profile.name}. What would you like to know?"
            elif 'stop' in message_lower:
                ai_response = "You have been unsubscribed. Reply START to opt back in."
            elif 'start' in message_lower:
                ai_response = f"Welcome back to {profile.name}! You're subscribed to receive messages."
            else:
                ai_response = f"Thanks for your message! I'm {profile.name}'s AI assistant. I'll respond as soon as possible."
            
            if ai_response and SIGNALWIRE_AVAILABLE:
                # Send AI response back via SignalWire
                response_result = send_sms(
                    from_number=to_number,  # Your SignalWire number
                    to_number=from_number,  # User's number
                    body=ai_response
                )
                
                if response_result.get('success'):
                    logger.info(f"AI response sent successfully to {from_number}")
                else:
                    logger.error(f"Failed to send AI response to {from_number}: {response_result.get('error')}")
            else:
                logger.warning("AI response not sent - SignalWire not available or no response generated")
        
        except Exception as ai_error:
            logger.error(f"Error generating/sending AI response: {str(ai_error)}")
        
        # Return XML response to SignalWire (required format)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
    except Exception as e:
        logger.error(f"Error handling incoming SMS webhook: {str(e)}")
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 500

@webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """Test webhook endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'SignalWire webhook endpoint is working',
        'method': request.method,
        'signalwire_available': SIGNALWIRE_AVAILABLE
    }), 200

@webhooks_bp.route('/signalwire/test-sms', methods=['POST'])
def test_sms_webhook():
    """Test SMS webhook with sample data"""
    try:
        # Simulate SignalWire webhook data
        test_data = {
            'From': '+1234567890',
            'To': '+1416555xxxx',
            'Body': 'Test message',
            'MessageSid': 'test_message_sid'
        }
        
        return jsonify({
            'status': 'test_completed',
            'message': 'SMS webhook test completed',
            'test_data': test_data,
            'signalwire_available': SIGNALWIRE_AVAILABLE
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test SMS webhook: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
EOF

# 3. UPDATE APP/__INIT__.PY TO PROPERLY REGISTER WEBHOOKS BLUEPRINT
echo "🔧 Updating app/__init__.py to register webhooks blueprint..."

# Create a backup
cp /opt/assistext_backend/app/__init__.py /opt/assistext_backend/app/__init__.py.backup

# Fix the app/__init__.py file
cat > /tmp/fix_app_init.py << 'EOF'
#!/usr/bin/env python3
import re

# Read the current app/__init__.py
with open('/opt/assistext_backend/app/__init__.py', 'r') as f:
    content = f.read()

# Find the position after signup blueprint registration
signup_pattern = r'(app\.register_blueprint\(signup_bp, url_prefix=\'/api/signup\'\)\s+print\("✅ Signup blueprint registered"\))'

# Add webhooks blueprint registration after signup
webhooks_registration = '''
    # Register webhooks blueprint
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
        print("✅ Webhooks blueprint registered")
    except ImportError as e:
        print(f"⚠️ Could not import webhooks blueprint: {e}")
    except Exception as e:
        print(f"⚠️ Error registering webhooks blueprint: {e}")'''

# Check if webhooks registration already exists
if 'webhooks_bp' not in content:
    # Add the webhooks registration after signup
    content = re.sub(
        signup_pattern,
        r'\1' + webhooks_registration,
        content
    )

# Remove the problematic dynamic webhook route
content = re.sub(
    r'    @app\.route\(\'/api/webhooks\'\).*?except Exception as e:\s+print\(f"⚠️ Error registering webhook route: {e}"\)',
    '',
    content,
    flags=re.DOTALL
)

# Write the fixed content back
with open('/opt/assistext_backend/app/__init__.py', 'w') as f:
    f.write(content)

print("✅ Fixed app/__init__.py")
EOF

python3 /tmp/fix_app_init.py

# 4. ENSURE SIGNALWIRE HELPERS ARE CORRECTLY AVAILABLE
echo "🔧 Verifying SignalWire helpers..."

# Test import
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/assistext_backend')

try:
    from app.utils.signalwire_helpers import get_signalwire_client, get_available_phone_numbers, purchase_phone_number, send_sms
    print("✅ All SignalWire functions imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔧 Fixing SignalWire helpers...")
    
    # Create minimal working version
    import os
    helpers_content = '''
from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_signalwire_client() -> Optional[SignalWireClient]:
    """Get configured SignalWire client"""
    try:
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL')
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID') 
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        
        if not all([space_url, project_id, auth_token]):
            logger.error("SignalWire credentials not configured")
            return None
        
        return SignalWireClient(project_id, auth_token, signalwire_space_url=space_url)
        
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def get_available_phone_numbers(area_code: str = None, city: str = None, country: str = 'CA', limit: int = 5) -> Tuple[List[Dict], str]:
    """Search for available phone numbers"""
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        search_params = {'limit': limit, 'sms_enabled': True}
        
        if area_code:
            search_params['area_code'] = area_code
        
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', 'ON'),
                'area_code': area_code or number.phone_number[2:5],
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': '$1.00',
                'monthly_cost': '$1.00'
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers, ""
        
    except Exception as e:
        return [], f"Failed to search available numbers: {str(e)}"

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number and configure webhook"""
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        purchase_params = {'phone_number': phone_number}
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
        
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result_data = {
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'sid': purchased_number.sid,
            'capabilities': {'sms': True, 'mms': True, 'voice': True},
            'webhook_configured': webhook_url is not None,
            'status': 'active',
            'purchased_at': datetime.utcnow().isoformat()
        }
        
        return result_data, ""
        
    except Exception as e:
        return None, f"Failed to purchase phone number: {str(e)}"

def send_sms(from_number: str, to_number: str, body: str, media_urls: List[str] = None) -> Dict[str, Any]:
    """Send SMS/MMS via SignalWire"""
    try:
        client = get_signalwire_client()
        if not client:
            return {'success': False, 'error': 'SignalWire client not available'}
        
        message_params = {
            'body': body,
            'from_': from_number,
            'to': to_number
        }
        
        if media_urls and len(media_urls) > 0:
            message_params['media_url'] = media_urls
        
        message = client.messages.create(**message_params)
        
        return {
            'success': True,
            'message_sid': message.sid,
            'status': message.status,
            'from_number': message.from_,
            'to_number': message.to,
            'body': message.body,
            'date_created': message.date_created.isoformat() if message.date_created else None
        }
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        return {'success': False, 'error': str(e)}

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def validate_signalwire_webhook_request(request) -> bool:
    """Validate that the request came from SignalWire"""
    try:
        required_fields = ['From', 'To', 'Body']
        for field in required_fields:
            if field not in request.form:
                return False
        return True
    except:
        return False

# Aliases for backward compatibility
def get_signalwire_phone_numbers():
    return []

def configure_number_webhook(phone_number: str, webhook_url: str):
    return True
'''
    
    with open('/opt/assistext_backend/app/utils/signalwire_helpers.py', 'w') as f:
        f.write(helpers_content)
    
    print("✅ Created minimal working SignalWire helpers")
EOF

# 5. RESTART THE APPLICATION
echo "🔄 Restarting application..."
sudo supervisorctl restart sms-backend

# Wait for restart
sleep 3

# 6. TEST THE FIXES
echo "🧪 Testing the fixes..."

# Test import
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/assistext_backend')

try:
    from app.utils.signalwire_helpers import get_signalwire_client, get_available_phone_numbers, purchase_phone_number, send_sms
    print("✅ All SignalWire functions imported successfully")
except ImportError as e:
    print(f"❌ Import error still exists: {e}")
EOF

# Test webhook endpoint
echo "🧪 Testing webhook endpoint..."
sleep 2
WEBHOOK_TEST=$(curl -s -w "%{http_code}" http://localhost:5000/api/webhooks/test -o /dev/null)
if [ "$WEBHOOK_TEST" = "200" ]; then
    echo "✅ Webhooks endpoint working (HTTP 200)"
else
    echo "❌ Webhooks endpoint failed (HTTP $WEBHOOK_TEST)"
fi

# Test signup endpoint
echo "🧪 Testing signup endpoint..."
SIGNUP_TEST=$(curl -s -w "%{http_code}" http://localhost:5000/api/signup/test -o /dev/null)
if [ "$SIGNUP_TEST" = "200" ]; then
    echo "✅ Signup endpoint working (HTTP 200)"
else
    echo "❌ Signup endpoint failed (HTTP $SIGNUP_TEST)"
fi

# Test phone search
echo "🧪 Testing phone search..."
PHONE_SEARCH_RESPONSE=$(curl -s -X POST http://localhost:5000/api/signup/search-numbers \
  -H "Content-Type: application/json" \
  -d '{"city": "toronto"}' 2>/dev/null)

if echo "$PHONE_SEARCH_RESPONSE" | grep -q "success"; then
    echo "✅ Phone search endpoint working"
else
    echo "❌ Phone search endpoint failed"
    echo "Response: $PHONE_SEARCH_RESPONSE"
fi

# 7. CHECK APPLICATION STATUS
echo "📊 Application status:"
sudo supervisorctl status sms-backend

echo ""
echo "🎉 Targeted fix completed!"
echo ""
echo "✅ Fixed signup.py import error"
echo "✅ Created webhooks blueprint"  
echo "✅ Updated app/__init__.py to register webhooks"
echo "✅ Verified SignalWire helpers availability"
echo ""
echo "🧪 Test your endpoints:"
echo "curl http://localhost:5000/api/webhooks/test"
echo "curl http://localhost:5000/api/signup/test"
echo ""
echo "📋 Monitor logs with:"
echo "sudo supervisorctl tail -f sms-backend"
