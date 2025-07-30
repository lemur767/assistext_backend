from flask import Blueprint, jsonify
from app.extensions import db
from app.models.user import User
from app.models.profile import Profile
from app.models.messaging import Message
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint"""
    checks = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'AssisText Backend',
        'checks': {}
    }
    
    # Database check
    try:
        result = db.engine.execute('SELECT 1').fetchone()
        if result:
            checks['checks']['database'] = 'healthy'
        else:
            checks['checks']['database'] = 'unhealthy: no result'
            checks['status'] = 'unhealthy'
    except Exception as e:
        checks['checks']['database'] = f'unhealthy: {str(e)}'
        checks['status'] = 'unhealthy'
    
    # Check table access
    try:
        user_count = User.query.count()
        profile_count = Profile.query.count()
        message_count = Message.query.count()
        
        checks['checks']['tables'] = 'healthy'
        checks['stats'] = {
            'users': user_count,
            'profiles': profile_count,
            'messages': message_count
        }
    except Exception as e:
        checks['checks']['tables'] = f'unhealthy: {str(e)}'
        checks['status'] = 'unhealthy'
    
    # SignalWire integration check
    try:
        signalwire_status = get_signalwire_integration_status()
        if signalwire_status['status'] == 'connected':
            checks['checks']['signalwire'] = 'healthy'
            checks['signalwire_info'] = {
                'phone_numbers': signalwire_status.get('phone_numbers_count', 0),
                'webhooks_configured': signalwire_status.get('webhooks_configured', 0)
            }
        else:
            checks['checks']['signalwire'] = f"unhealthy: {signalwire_status.get('error', 'connection failed')}"
            checks['status'] = 'degraded'  # SignalWire issues shouldn't mark entire service as unhealthy
    except Exception as e:
        checks['checks']['signalwire'] = f'error: {str(e)}'
        checks['status'] = 'degraded'
    
    # Determine HTTP status code
    if checks['status'] == 'healthy':
        status_code = 200
    elif checks['status'] == 'degraded':
        status_code = 200  # Still operational, just some features affected
    else:
        status_code = 503
    
    return jsonify(checks), status_code

@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Kubernetes/Docker readiness probe"""
    try:
        # Check if database is accessible
        db.engine.execute('SELECT 1')
        
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Kubernetes/Docker liveness probe"""
    return jsonify({
        'status': 'alive',
        'service': 'AssisText Backend',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@health_bp.route('/version', methods=['GET'])
def version_info():
    """Get version and build information"""
    return jsonify({
        'service': 'AssisText Backend',
        'version': '1.0.0',
        'build_date': '2025-06-11',
        'environment': 'production',
        'integrations': {
            'signalwire': 'enabled',
            'llm': 'ollama',
            'database': 'postgresql',
            'cache': 'redis'
        }
    }), 200
