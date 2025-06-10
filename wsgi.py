from flask import Flask, jsonify
from datetime import datetime
import os

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import SignalWire integration
from signalwire_integration import SignalWireService, create_signalwire_blueprint

# Create Flask app
app = Flask(__name__)

# Configure app with SignalWire settings
app.config.update({
    'SIGNALWIRE_PROJECT_ID': os.getenv('SIGNALWIRE_PROJECT_ID'),
    'SIGNALWIRE_API_TOKEN': os.getenv('SIGNALWIRE_API_TOKEN'),
    'SIGNALWIRE_SPACE_URL': os.getenv('SIGNALWIRE_SPACE_URL'),
    'BASE_URL': os.getenv('BASE_URL', 'https://backend.assitext.ca')
})

# Initialize SignalWire service
signalwire_service = SignalWireService(app)

# Register SignalWire blueprint
signalwire_bp = create_signalwire_blueprint(signalwire_service)
app.register_blueprint(signalwire_bp, url_prefix='/api')

# Store service for global access
app.signalwire_service = signalwire_service

# Main routes
@app.route('/')
def index():
    return jsonify({
        'message': 'AssisText Backend with SignalWire',
        'status': 'running',
        'signalwire_configured': signalwire_service.client is not None,
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': {
            'health': '/health',
            'webhook': '/api/webhooks/signalwire', 
            'send_sms': '/api/sms/send',
            'test_signalwire': '/api/signalwire/test'
        }
    })

@app.route('/health')
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'assistext-backend',
        'signalwire_ready': signalwire_service.client is not None,
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
