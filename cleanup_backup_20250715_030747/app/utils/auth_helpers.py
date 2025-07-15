from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models.user import User
from app.models.subscription import Subscription

def require_subscription(allowed_statuses: List[str] = None):
    """Decorator to require specific subscription status"""
    if allowed_statuses is None:
        allowed_statuses = ['active', 'trialing']
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            
            subscription = Subscription.query.filter_by(
                user_id=current_user_id
            ).first()
            
            if not subscription or subscription.status not in allowed_statuses:
                return jsonify({
                    'error': 'Valid subscription required',
                    'required_statuses': allowed_statuses
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_signalwire_setup():
    """Decorator to require completed SignalWire setup"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            
            user = User.query.get(current_user_id)
            if not user or not user.signalwire_setup_completed:
                return jsonify({
                    'error': 'SignalWire setup required',
                    'setup_url': '/api/onboarding/search-numbers'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
