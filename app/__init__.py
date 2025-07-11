# app/__init__.py
"""
Flask application factory
Fixed to prevent circular imports and duplicate blueprint registrations
"""
import logging
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name=None):
    """
    Application factory pattern
    """
    print("🚀 Creating Flask app...")
    
    # Create Flask app
    app = Flask(__name__)
    print(f"✅ Flask app created: {type(app)}")
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')
    
    # Load config safely
    configure_app(app, config_name)
    
    configure_cors(app)
    # Initialize extensions
    initialize_extensions(app)
    
    # Import models after extensions are initialized
    # This prevents circular imports
    with app.app_context():
        import_models()
    
    # Set up JWT handlers
    setup_jwt_handlers(app)
    
    # Register error handlers
    setup_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Add health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'message': 'API is running'})
      # ✅ CORS FIX: Add options handler for all routes
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = jsonify({'status': 'ok'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
            response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
            return response

    @app.after_request  
    def after_request(response):
        origin = request.headers.get('Origin')
        if origin:
            response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    print("✅ Flask app fully initialized")
    return app


def configure_app(app, config_name):
    """Configure the Flask app"""
    try:
        from app.config import get_config
        config = get_config(config_name)
        app.config.from_object(config)
        print(f"✅ Configuration loaded: {config_name}")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        # Set basic defaults
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://app_user:Assistext2025Secure@localhost/assistext_prod')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13')

def configure_cors(app):  

    print("🔧 Configuring CORS...")
    
    # Development origins
    dev_origins = [
        "http://localhost:3000",      # React dev server
        "http://localhost:5173",      # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # Production origins
    prod_origins = [
        "https://assitext.ca",
        "https://www.assitext.ca",
        "https://app.assitext.ca"
    ]
    
    # All allowed origins
    allowed_origins = dev_origins + prod_origins
    
    # Configure CORS with comprehensive settings
    CORS(app, 
         origins=allowed_origins,
         allow_headers=[
             "Content-Type",
             "Authorization", 
             "X-Requested-With",
             "Accept",
             "Origin"
         ],
         methods=[
             "GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"
         ],
         supports_credentials=True,
         max_age=86400,  # 24 hours
         vary_header=True
    )
    
    print(f"✅ CORS configured for origins: {allowed_origins}")


def initialize_extensions(app):
    """Initialize Flask extensions"""
    print("🔧 Initializing extensions...")
    try:
        from app.extensions import db, migrate, jwt
        
        # Initialize CORS
        CORS(app, origins=[
            "http://localhost:3000", 
            "http://localhost:5173",
            "https://assitext.ca",
            "https://www.assitext.ca"
        ])
        
        # Initialize database
        db.init_app(app)
        migrate.init_app(app, db)
        
        # Initialize JWT
        jwt.init_app(app)
        
        print("✅ Extensions initialized")
    except Exception as e:
        print(f"❌ Extensions failed: {e}")
        raise


def import_models():
    """
    Import models after extensions are initialized
    This prevents circular imports and ensures proper table creation
    """
    try:
        # Import all models in the correct order
        from app.models import (
            User, Subscription, SubscriptionPlan, Message, Client,
            Invoice, InvoiceItem, PaymentMethod, Payment,
            CreditTransaction, BillingSettings, UsageRecord,
            ActivityLog, NotificationLog, MessageTemplate
        )
        print("✅ Models imported successfully")
    except Exception as e:
        print(f"❌ Model import failed: {e}")
        # Continue anyway - some models may be optional


def setup_jwt_handlers(app):
    """Set up JWT error handlers"""
    try:
        from app.extensions import jwt
        
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return jsonify({'message': 'Token has expired'}), 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return jsonify({'message': 'Invalid token'}), 401
        
        @jwt.unauthorized_loader
        def unauthorized_callback(error):
            return jsonify({'message': 'Authorization required'}), 401
        
        print("✅ JWT handlers set up")
    except Exception as e:
        print(f"❌ JWT handlers failed: {e}")


def setup_error_handlers(app):
    """Set up error handlers"""
    try:
        @app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Not found'}), 404
        
        @app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500
        
        print("✅ Error handlers set up")
    except Exception as e:
        print(f"❌ Error handlers failed: {e}")


def register_blueprints(app):
    """
    Register blueprints safely
    Fixed to prevent duplicate registrations and circular imports
    """
    print("🔧 Registering blueprints...")
    
    # Track registered blueprints to prevent duplicates
    registered_blueprints = set()
    blueprints_registered = 0
    
    # Define blueprints in priority order
    blueprint_configs = [
        # Core blueprints (required)
        ('app.api.auth', 'auth_bp', '/api/auth', True),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks', True),
        ('app.api.billing', 'billing_bp', '/api/billing', True),
        
        # Additional blueprints (optional)
        ('app.api.messages', 'messages_bp', '/api/messages', False),
        ('app.api.clients', 'clients_bp', '/api/clients', False),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire', False),
        ('app.api.user_profile', 'user_profile_bp', '/api/user/profile', False),
    ]
    
    for module_name, blueprint_name, url_prefix, is_required in blueprint_configs:
        if blueprint_name in registered_blueprints:
            print(f"⚠️  Blueprint {blueprint_name} already registered, skipping")
            continue
            
        try:
            # Import the module
            module = __import__(module_name, fromlist=[blueprint_name])
            
            # Get the blueprint object
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                
                # Verify it's a blueprint
                if hasattr(blueprint, 'register'):
                    app.register_blueprint(blueprint, url_prefix=url_prefix)
                    registered_blueprints.add(blueprint_name)
                    blueprints_registered += 1
                    logger.info(f"✅ {blueprint_name} registered at {url_prefix}")
                else:
                    logger.warning(f"⚠️  {blueprint_name} is not a valid blueprint")
            else:
                if is_required:
                    logger.error(f"❌ Required blueprint {blueprint_name} not found in {module_name}")
                else:
                    logger.info(f"⚠️  Optional blueprint {blueprint_name} not found in {module_name}")
                    
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
    return blueprints_registered