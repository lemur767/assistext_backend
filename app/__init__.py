# app/__init__.py
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import logging
import os

from app.config import config
from app.extensions import init_extensions, db, jwt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name='production'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
     
    # Initialize extensions
    init_extensions(app)
   
    
    # Register error handlers first
    register_error_handlers(app)
    
    # Register basic routes (including health check)
    register_basic_routes(app)
    
    # Import models and create tables
    with app.app_context():
        setup_database(app)
    
    # Register blueprints
    register_blueprints(app)
    
    logger.info(f"Flask app created successfully in {config_name} mode")
    return app


def setup_database(app):
    """Set up database models and tables"""
    try:
        # Clear any existing metadata to prevent conflicts
        db.metadata.clear()
        
        # Import models in safe order
        logger.info("Importing models...")
        from app.models.user import User
        logger.info("✓ User model imported")
        
        # Create all tables
        db.create_all()
        logger.info("✅ Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Database setup error: {e}")
        # Try to create basic tables anyway
        try:
            db.create_all()
            logger.info("✅ Basic database tables created")
        except Exception as e2:
            logger.error(f"❌ Critical database error: {e2}")


def register_basic_routes(app):
    """Register basic application routes"""
    
    @app.route('/')
    def index():
        return {'message': 'Backend Assistext', 'status': 'running'}, 200
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring"""
        try:
            # Test database connection
            db.engine.execute('SELECT 1')
            db_status = 'connected'
        except Exception as e:
            db_status = f'error: {str(e)}'
        
        return {
            'status': 'ok',
            'message': 'Backend is running',
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
    
    
    try:
        from app.api.profile import profile_bp
        app.register_blueprint(profile_bp, url_prefix='/api/profile')
        logger.info("✅ Profiles blueprint registered")
    except Exception as e:
        logger.warning(f"⚠️ Profiles blueprint not available: {e}")
    
    try:
        from app.api.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        logger.info("✅ Messages blueprint registered")
    except Exception as e:
        logger.warning(f"⚠️ Messages blueprint not available: {e}")
    


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
    logger.info("Starting production server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
