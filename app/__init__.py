import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import get_config
from app.extensions import db, migrate, jwt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name=None):
       
    print("🚀 Creating Flask app...")
    
    # Create Flask app
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
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails