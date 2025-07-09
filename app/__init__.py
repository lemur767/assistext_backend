import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import get_config
from app.extensions import db, migrate, jwt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name='production'):
       
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')
    
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions
    CORS(app, origins=["http://localhost:3000", "http://localhost:5173","https://assitext.ca","https://www.assitext.ca"])  # Add your frontend URLs
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Set up JWT handlers
    setup_jwt_handlers(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Set up database
    setup_database(app)
    
    logger.info("Flask app created successfully")
    return app


def setup_jwt_handlers(app):
   
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired', 'message': 'Please log in again'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token', 'message': 'Please provide a valid token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization required', 'message': 'Please provide an access token'}), 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has been revoked', 'message': 'Please log in again'}), 401
    
    logger.info("JWT handlers configured")


def register_error_handlers(app):
    
    
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify({'error': 'Bad request'}), 400
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({'error': 'Unauthorized'}), 401
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({'error': 'Forbidden'}), 403
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        return jsonify({'error': 'Rate limit exceeded', 'message': 'Too many requests'}), 429


def register_blueprints(app):
   
    
    blueprints_registered = 0
    
    # Core blueprints (required)
    core_blueprints = [
        ('app.api.auth', 'auth_bp', '/api/auth', True),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks', True),
        ('app.api.billing', 'billing_bp', '/api/billing', True),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire', True),
    ]
    
    # Updated blueprints (new structure)
    updated_blueprints = [
        ('app.api.user_profile', 'user_profile_bp', '/api/user/profile', False),  # NEW: Single profile endpoint
        ('app.api.clients', 'clients_bp', '/api/clients', False),
        ('app.api.messages', 'messages_bp', '/api/messages', False),
    ]
    
        
    # Register all blueprints
    all_blueprints = core_blueprints + updated_blueprints
    
    for module_name, blueprint_name, url_prefix, is_required in all_blueprints:
        try:
            # Import the module
            module = __import__(module_name, fromlist=[blueprint_name])
            
            # Get the blueprint object
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                
                # Register the blueprint
                app.register_blueprints(blueprint, url_prefix=url_prefix)
                logger.info(f"✅ {blueprint_name} registered at {url_prefix}")
                blueprints_registered += 1
            else:
                logger.warning(f"⚠️  {module_name} found but {blueprint_name} not available")
                
        except ImportError as e:
            if is_required:
                logger.error(f"❌ Required blueprint {blueprint_name} could not be imported: {e}")
            else:
                logger.info(f"⚠️  Optional blueprint {blueprint_name} not available: {e}")
                
        except Exception as e:
            if is_required:
                logger.error(f"❌ Error registering required blueprint {blueprint_name}: {e}")
            else:
                logger.warning(f"⚠️  Error registering optional blueprint {blueprint_name}: {e}")
    
    logger.info(f"📊 Total blueprints registered: {blueprints_registered}")
    
    # Add health check endpoint
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'healthy',
            'blueprints_registered': blueprints_registered,
            'timestamp': app.config.get('START_TIME', 'unknown')
        }
    
    return blueprints_registered


# Legacy function for compatibility (if needed)
def get_blueprint_by_name(name):
    """
    Legacy function - kept for compatibility
    Returns None instead of causing tuple errors
    """
    logger.warning(f"get_blueprint_by_name({name}) called - this function is deprecated")
    return None


# List available blueprints for introspection


def setup_database(app):
    """Set up database models and tables"""
    try:
        # Import models to register them with SQLAlchemy
        from app.models import User, Client, Message, FlaggedMessage
        
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            logger.info("Database tables created/verified")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails


# Health check endpoint
def add_health_check(app):
    """Add health check endpoint"""
    
    @app.route('/health')
    def health_check():
        try:
            # Test database connection
            from app.models import User
            User.query.first()
            
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    @app.route('/api/health/blueprints')
    def blueprint_health():
        """Check which blueprints are loaded"""
        loaded_blueprints = list(app.blueprints.keys())
        
        expected_blueprints = ['auth', 'profile', 'clients', 'messages', 'webhooks']
        missing_blueprints = [bp for bp in expected_blueprints if bp not in loaded_blueprints]
        
        status = 'healthy' if not missing_blueprints else 'degraded'
        
        return jsonify({
            'status': status,
            'loaded_blueprints': loaded_blueprints,
            'missing_blueprints': missing_blueprints,
            'total_loaded': len(loaded_blueprints)
        }), 200


# For backwards compatibility with existing deployment scripts
def create_application():
    """Alternative entry point for WSGI servers"""
    return create_app()


# Add health checks if requested
def create_app_with_health_checks(config_name=None):
    """Create app with health check endpoints"""
    app = create_app(config_name)
    add_health_check(app)
    return app
AVAILABLE_BLUEPRINTS = [
    'auth_bp',
    'profile_bp', 
    'clients_bp',
    'messages_bp',
    'webhooks_bp'
]

__all__ = [
    'register_blueprints',
    'get_blueprint_by_name',
    'AVAILABLE_BLUEPRINTS'
]


if __name__ == '__main__':
    # For development server
    app = create_app('production')
    add_health_check(app)
    app.run(debug=True, host='0.0.0.0', port=5000)