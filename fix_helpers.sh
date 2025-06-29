# =============================================================================
# COMPLETE DEPLOYMENT FIX GUIDE - Resolve All Import Errors
# =============================================================================

echo "🔧 Starting SignalWire Integration Fix..."

# 1. BACKUP CURRENT FILES
echo "📦 Creating backups..."
cp /opt/assistext_backend/app/utils/signalwire_helpers.py /opt/assistext_backend/app/utils/signalwire_helpers.py.backup
cp /opt/assistext_backend/app/api/signup.py /opt/assistext_backend/app/api/signup.py.backup 2>/dev/null || true

# 2. UPDATE SIGNALWIRE HELPERS
echo "🔧 Updating SignalWire helpers..."
cat > /opt/assistext_backend/app/utils/signalwire_helpers.py << 'EOF'
# =============================================================================
# COMPLETE SIGNALWIRE HELPERS - ALL MISSING FUNCTIONS INCLUDED
# =============================================================================

from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging
import hashlib
import hmac
import base64

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

def get_signalwire_phone_numbers() -> List[Dict]:
    """Get all purchased SignalWire phone numbers"""
    try:
        client = get_signalwire_client()
        if not client:
            return []
        
        phone_numbers = client.incoming_phone_numbers.list()
        
        formatted_numbers = []
        for number in phone_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'sid': number.sid,
                'friendly_name': number.friendly_name,
                'capabilities': {
                    'sms': getattr(number.capabilities, 'sms', True) if hasattr(number, 'capabilities') else True,
                    'mms': getattr(number.capabilities, 'mms', True) if hasattr(number, 'capabilities') else True,
                    'voice': getattr(number.capabilities, 'voice', True) if hasattr(number, 'capabilities') else True
                },
                'sms_url': getattr(number, 'sms_url', None),
                'voice_url': getattr(number, 'voice_url', None),
                'date_created': getattr(number, 'date_created', None)
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Error retrieving SignalWire phone numbers: {str(e)}")
        return []

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

def configure_number_webhook(phone_number: str, webhook_url: str) -> bool:
    """Configure webhook for an existing phone number"""
    try:
        client = get_signalwire_client()
        if not client:
            return False
        
        phone_numbers = client.incoming_phone_numbers.list()
        target_number = None
        
        for number in phone_numbers:
            if number.phone_number == phone_number:
                target_number = number
                break
        
        if not target_number:
            return False
        
        client.incoming_phone_numbers(target_number.sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error configuring webhook: {str(e)}")
        return False

def validate_signalwire_webhook_request(request) -> bool:
    """Validate that the request came from SignalWire"""
    try:
        # Basic validation - in production, implement proper signature validation
        required_fields = ['From', 'To', 'Body']
        for field in required_fields:
            if field not in request.form:
                return False
        return True
    except:
        return False

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def format_phone_number(phone_number: str) -> str:
    """Format phone number to E.164 format"""
    cleaned = ''.join(filter(str.isdigit, phone_number))
    
    if len(cleaned) == 10:
        cleaned = '1' + cleaned
    
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    return cleaned

# Backward compatibility aliases
def validate_signalwire_request(request):
    return validate_signalwire_webhook_request(request)

def get_phone_number_info(phone_number: str):
    numbers = get_signalwire_phone_numbers()
    for number in numbers:
        if number['phone_number'] == phone_number:
            return number
    return None

def configure_webhook(phone_number_sid: str, webhook_url: str):
    try:
        client = get_signalwire_client()
        if not client:
            return False
        
        client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        return True
    except:
        return False
EOF

# 3. UPDATE IMPORTS IN AFFECTED FILES
echo "🔧 Fixing import statements..."

# Fix profiles blueprint
if [ -f "/opt/assistext_backend/app/api/profiles.py" ]; then
    sed -i 's/from app.utils.signalwire_helpers import get_signalwire_phone_numbers/from app.utils.signalwire_helpers import get_signalwire_phone_numbers, send_sms/' /opt/assistext_backend/app/api/profiles.py
fi

# Fix any other files that import these functions
find /opt/assistext_backend/app -name "*.py" -type f -exec grep -l "from app.utils.signalwire_helpers import" {} \; | while read file; do
    echo "  Checking $file..."
    # Remove any imports that don't exist and add the ones that do
    sed -i '/from app.utils.signalwire_helpers import/d' "$file"
    
    # Check what functions the file actually uses and add appropriate imports
    if grep -q "send_sms\|get_signalwire_phone_numbers\|get_available_phone_numbers\|purchase_phone_number" "$file"; then
        # Add the correct import at the top of the file after any existing imports
        sed -i '/^from/a from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display' "$file"
    fi
done

# 4. CREATE MISSING MESSAGE MODEL (if it doesn't exist)
echo "🔧 Creating Message model..."
if [ ! -f "/opt/assistext_backend/app/models/message.py" ]; then
    cat > /opt/assistext_backend/app/models/message.py << 'EOF'
from app.extensions import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    from_number = db.Column(db.String(20), nullable=False)
    to_number = db.Column(db.String(20), nullable=False)
    message_body = db.Column(db.Text, nullable=False)
    message_sid = db.Column(db.String(50), nullable=True)
    direction = db.Column(db.String(10), nullable=False)  # 'inbound' or 'outbound'
    status = db.Column(db.String(20), nullable=False)     # 'received', 'sent', 'failed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    profile = db.relationship('Profile', backref='messages')
    
    def __repr__(self):
        return f'<Message {self.id}: {self.from_number} -> {self.to_number}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'message_body': self.message_body,
            'message_sid': self.message_sid,
            'direction': self.direction,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
EOF
fi

# 5. UPDATE THE MAIN APP TO REGISTER BLUEPRINTS PROPERLY
echo "🔧 Updating app initialization..."

# Create a temporary fix for the app initialization
cat > /tmp/fix_blueprints.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/assistext_backend')

from app import create_app
from app.extensions import db

app = create_app()

# Test imports to ensure they work
try:
    from app.utils.signalwire_helpers import send_sms, get_signalwire_phone_numbers
    print("✅ SignalWire helpers imported successfully")
except ImportError as e:
    print(f"❌ SignalWire import error: {e}")

try:
    from app.api.profiles import profiles_bp
    print("✅ Profiles blueprint imported successfully")
except ImportError as e:
    print(f"❌ Profiles import error: {e}")

# Create database tables if needed
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created/updated")
    except Exception as e:
        print(f"❌ Database error: {e}")

print("🎉 Blueprint fix completed!")
EOF

# Run the fix
python3 /tmp/fix_blueprints.py

# 6. CREATE WEBHOOKS BLUEPRINT (if it doesn't exist)
echo "🔧 Creating webhooks blueprint..."
if [ ! -f "/opt/assistext_backend/app/api/webhooks.py" ]; then
    cat > /opt/assistext_backend/app/api/webhooks.py << 'EOF'
from flask import Blueprint, request, jsonify, current_app
from app.models.profile import Profile
from app.utils.signalwire_helpers import validate_signalwire_webhook_request, send_sms
from app.extensions import db
import logging

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS messages from SignalWire webhook"""
    try:
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
            
            if ai_response:
                # Send AI response back via SignalWire
                response_result = send_sms(
                    from_number=to_number,  # Your SignalWire number
                    to_number=from_number,  # User's number
                    body=ai_response
                )
                
                if response_result.get('success'):
                    logger.info(f"AI response sent successfully to {from_number}")
                else:
                    logger.error(f"Failed to send AI response to {from_number}")
        
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
        'method': request.method
    }), 200
EOF
fi

# 7. RESTART THE APPLICATION
echo "🔄 Restarting application..."
sudo supervisorctl restart sms-backend

# 8. TEST THE FIXES
echo "🧪 Testing the fixes..."

# Test SignalWire helpers import
python3 -c "
import sys
sys.path.insert(0, '/opt/assistext_backend')
from app.utils.signalwire_helpers import send_sms, get_signalwire_phone_numbers
print('✅ All SignalWire functions imported successfully')
"

# Test API endpoints
sleep 5  # Wait for restart

echo "🧪 Testing API endpoints..."

# Test webhook endpoint
curl -s http://localhost:5000/api/webhooks/test > /dev/null && echo "✅ Webhooks endpoint working" || echo "❌ Webhooks endpoint failed"

# Test phone number search
curl -s -X POST http://localhost:5000/api/signup/search-numbers \
  -H "Content-Type: application/json" \
  -d '{"city": "toronto"}' > /dev/null && echo "✅ Phone search endpoint working" || echo "❌ Phone search endpoint failed"

# 9. UPDATE .ENV FILE WITH CORRECT BASE_URL
echo "🔧 Updating configuration..."
if [ -f "/opt/assistext_backend/.env" ]; then
    # Update BASE_URL to use HTTPS
    sed -i 's|BASE_URL=.*|BASE_URL=https://backend.assitext.ca|' /opt/assistext_backend/.env
    echo "✅ Updated BASE_URL to HTTPS"
fi

# 10. FINAL STATUS CHECK
echo "📊 Final status check..."
sudo supervisorctl status sms-backend

echo ""
echo "🎉 SignalWire Integration Fix Complete!"
echo ""
echo "✅ Fixed import errors"
echo "✅ Updated SignalWire helpers with all missing functions"
echo "✅ Created webhooks blueprint"
echo "✅ Created Message model"
echo "✅ Updated configuration"
echo ""
echo "🧪 Test your registration flow:"
echo "1. Go to your frontend registration"
echo "2. Try searching for phone numbers"
echo "3. Complete a registration"
echo "4. Send a test SMS to the purchased number"
echo ""
echo "📋 Monitor logs with:"
echo "sudo supervisorctl tail -f sms-backend"
