# SignalWire Integration for AssisText
from flask import request, jsonify, current_app, Blueprint
from datetime import datetime
import os

try:
    from signalwire.rest import Client as SignalWireClient
except ImportError:
    print("SignalWire package not installed")
    SignalWireClient = None

class SignalWireService:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.project_id = app.config.get('SIGNALWIRE_PROJECT_ID')
        self.api_token = app.config.get('SIGNALWIRE_API_TOKEN') 
        self.space_url = app.config.get('SIGNALWIRE_SPACE_URL')
        
        if SignalWireClient and self.project_id and self.api_token and self.space_url:
            self.client = SignalWireClient(
                self.project_id, 
                self.api_token, 
                signalwire_space_url=self.space_url
            )
        else:
            self.client = None
            print("Warning: SignalWire client not initialized")
    
    def validate_webhook(self, request):
        required_fields = ['Body', 'From', 'To']
        for field in required_fields:
            if field not in request.form:
                return False, f"Missing field: {field}"
        return True, "Valid"
    
    def send_sms(self, to_number, from_number, message_body):
        try:
            if not self.client:
                return {"success": False, "error": "Client not initialized"}
            
            message = self.client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

def generate_auto_response(incoming_message):
    message_lower = incoming_message.lower().strip()
    
    if any(word in message_lower for word in ['hi', 'hello', 'hey']):
        return "Hello! Thanks for your message. I'll get back to you soon! 😊"
    elif any(word in message_lower for word in ['help', 'info']):
        return "Hi! For assistance, please visit our website. Thanks!"
    elif 'stop' in message_lower:
        return "You have been unsubscribed. Reply START to opt back in."
    elif 'start' in message_lower:
        return "Welcome back! You're subscribed to receive messages."
    else:
        return "Thanks for your message! I'll respond as soon as possible. 💕"

def create_signalwire_blueprint(signalwire_service):
    signalwire_bp = Blueprint('signalwire', __name__)
    
    @signalwire_bp.route('/webhooks/signalwire', methods=['POST'])
    def signalwire_webhook():
        try:
            # Validate webhook
            is_valid, msg = signalwire_service.validate_webhook(request)
            if not is_valid:
                return jsonify({"error": msg}), 400
            
            # Extract data
            message_body = request.form.get('Body', '').strip()
            from_number = request.form.get('From', '')
            to_number = request.form.get('To', '')
            
            print(f"📱 SMS Received: {from_number} -> {to_number}: {message_body}")
            
            # Generate and send auto-response
            auto_response = generate_auto_response(message_body)
            
            if auto_response:
                result = signalwire_service.send_sms(
                    to_number=from_number,
                    from_number=to_number,
                    message_body=auto_response
                )
                print(f"📤 Auto-response: {result}")
            
            return '', 204
            
        except Exception as e:
            print(f"❌ Webhook error: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    @signalwire_bp.route('/sms/send', methods=['POST'])
    def send_sms():
        try:
            data = request.get_json()
            required = ['to', 'from', 'message']
            
            for field in required:
                if field not in data:
                    return jsonify({"error": f"Missing: {field}"}), 400
            
            result = signalwire_service.send_sms(
                to_number=data['to'],
                from_number=data['from'],
                message_body=data['message']
            )
            
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @signalwire_bp.route('/signalwire/test', methods=['GET'])
    def test_signalwire():
        try:
            status = {
                "project_id": "✅" if signalwire_service.project_id else "❌",
                "api_token": "✅" if signalwire_service.api_token else "❌", 
                "space_url": signalwire_service.space_url or "❌",
                "client_ready": "✅" if signalwire_service.client else "❌",
                "timestamp": datetime.utcnow().isoformat()
            }
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return signalwire_bp
