import logging
<<<<<<< HEAD
import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import get_config
from app.extensions import db, migrate, jwt
=======

from app.config import config_map
from app.extensions import db, migrate, jwt, socketio, celery
>>>>>>> a9dc41c (...)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

<<<<<<< HEAD
def create_app(config_name=None):
       
    print("🚀 Creating Flask app...")
    
    # Create Flask app
=======

def create_app(config_name='production'):
    """Create and configure the Flask application"""
>>>>>>> a9dc41c (...)
    app = Flask(__name__)
    print(f"✅ Flask app created: {type(app)}")
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')
    
    try:
        config = get_config(config_name)
        app.config.from_object(config)
        print(f"✅ Configuration loaded: {config_name}")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        # Set basic defaults
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL','postgresql://app_user:Assistext2025Secure@localhost/assistext_prod')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    print("🔧 Initializing extensions...")
    try:
        CORS(app, origins=["http://localhost:3000", "http://localhost:5173","https://assitext.ca","https://www.assitext.ca"])
        db.init_app(app)
        migrate.init_app(app, db)
        jwt.init_app(app)
        print("✅ Extensions initialized")
    except Exception as e:
        print(f"❌ Extensions failed: {e}")
    
    # Set up JWT handlers
    try:
        setup_jwt_handlers(app)
        print("✅ JWT handlers set up")
    except Exception as e:
        print(f"❌ JWT handlers failed: {e}")
    
    # Register error handlers
    try:
        register_error_handlers(app)
        print("✅ Error handlers registered")
    except Exception as e:
        print(f"❌ Error handlers failed: {e}")
    
    # Register blueprints - THIS IS THE CRITICAL PART
    print("🔧 Registering blueprints...")
    print(f"   App type before blueprint registration: {type(app)}")
    print(f"   App has register_blueprint: {hasattr(app, 'register_blueprint')}")
    
    try:
        # Import the blueprint registration function
        from app.api import register_blueprints
        print(f"   ✅ Blueprint registration function imported: {register_blueprints}")
        
        # Call the function
        blueprint_count = register_blueprints(app)
        print(f"   ✅ {blueprint_count} blueprints registered")
        
    except Exception as e:
        print(f"   ❌ Blueprint registration failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Set up database
    try:
        setup_database(app)
        print("✅ Database set up")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
    
    # Add health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'SMS AI Backend'}
    
    logger.info("Flask app created successfully")
    return app


def setup_jwt_handlers(app):
    """Set up JWT error handlers"""
    
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
    """Register application error handlers"""
    
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


def setup_database(app):
    """Set up database models and tables"""
    try:
        # Import models to register them with SQLAlchemy
        from app.models import User, Client, Message
        
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            logger.info("Database tables created/verified")
        
<<<<<<< HEAD
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails
=======
        return {
            'status': 'ok',
            'message': 'Backend Running',
            'database': db_status,
            'version': '1.0.0'
        }, 200
    
    @app.route('/api/health')
    def api_health_check():
        """API-specific health check"""
        return {
            'status': 'ok',
            'message': 'API is healthy',
            'endpoints': [
                '/api/auth/register',
                '/api/auth/login',
                '/api/auth/test'
            ]
        }, 200


def register_blueprints(app):
    """Register Flask blueprints safely"""
    
    # Register auth blueprint (most critical)
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        logger.info("✅ Auth blueprint registered")
    except ImportError as e:
        logger.error(f"❌ Could not import auth blueprint: {e}")
        register_fallback_auth_routes(app)
    except Exception as e:
        logger.error(f"❌ Error registering auth blueprint: {e}")
        register_fallback_auth_routes(app)
    
    # Comment out other blueprints until auth works
    """
    try:
        from app.api.profiles import profiles_bp
        app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
        logger.info("✅ Profiles blueprint registered")
    except Exception as e:
        logger.warning(f"⚠️ Profiles blueprint not available: {e}")
    
    try:
        from app.api.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        logger.info("✅ Messages blueprint registered")
    except Exception as e:
        logger.warning(f"⚠️ Messages blueprint not available: {e}")
    """


def register_fallback_auth_routes(app):
    """Register fallback auth routes if the main auth blueprint fails"""
    logger.info("Registering fallback auth routes...")
    
    @app.route('/api/auth/register', methods=['POST'])
    def fallback_register():
        return {
            'error': 'Auth blueprint not available',
            'message': 'Check auth blueprint configuration'
        }, 503
    
    @app.route('/api/auth/login', methods=['POST'])
    def fallback_login():
        return {
            'error': 'Auth blueprint not available', 
            'message': 'Check auth blueprint configuration'
        }, 503
    
    @app.route('/api/auth/test', methods=['GET'])
    def fallback_auth_test():
        return {
            'error': 'Auth blueprint not available',
            'message': 'Using fallback routes'
        }, 503


def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return {
            'error': 'Endpoint not found',
            'message': 'The requested API endpoint does not exist'
        }, 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return {
            'error': 'Method not allowed',
            'message': 'The method is not allowed for the requested URL'
        }, 405
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return {
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }, 500
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token'}, 401


# For development server
if __name__ == '__main__':
    app = create_app('production')
    logger.info("Starting backend server, database and redis.")
    app.run(debug=True, host='0.0.0.0', port=5000)
>>>>>>> a9dc41c (...)
