

import logging
import os
from flask import Flask, jsonify
# from flask_cors import CORS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configure_cors(app):
    """
    Configure CORS with proper settings for all environments
    """
    # Determine environment
    environment = os.getenv('FLASK_ENV', 'development')
    
    if environment == 'development':
        # Development: Allow localhost on common ports
        allowed_origins = [
            "http://localhost:3000",    # Create React App default
            "http://localhost:5173",    # Vite default
            "http://localhost:3001",    # Alternative port
            "http://localhost:8080",    # Alternative port
            "http://127.0.0.1:3000",    # Local IP
            "http://127.0.0.1:5173",    # Local IP Vite
        ]
        
        print(f"🔧 CORS configured for DEVELOPMENT with origins: {allowed_origins}")
        
    else:
        # Production: Only allow your actual domains
        allowed_origins = [
            "https://assitext.ca",
            "https://www.assitext.ca",
            "https://backend.assitext.ca",
        ]
        
        print(f"🔒 CORS configured for PRODUCTION with origins: {allowed_origins}")
    
    # Configure CORS with comprehensive settings
    # CORS(app,
         origins=allowed_origins,
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
         allow_headers=[
             'Content-Type',
             'Authorization', 
             'X-Requested-With',
             'Accept',
             'Origin',
             'X-CSRF-Token',
             'X-Request-ID'
         ],
         expose_headers=[
             'Content-Range',
             'X-Content-Range',
             'X-Total-Count'
         ],
         supports_credentials=True,
         max_age=86400  # 24 hours for preflight cache
    )
    
    # Add manual OPTIONS handler for stubborn endpoints
    @app.before_request
    def handle_preflight():
        from flask import request, make_response
        
        if request.method == "OPTIONS":
            origin = request.headers.get('Origin')
            
            if origin in allowed_origins:
                response = make_response()
                response.headers.add("Access-Control-Allow-Origin", origin)
                response.headers.add('Access-Control-Allow-Headers', 
                                   'Content-Type,Authorization,X-Requested-With,Accept,Origin')
                response.headers.add('Access-Control-Allow-Methods', 
                                   'GET,PUT,POST,DELETE,OPTIONS,PATCH')
                response.headers.add('Access-Control-Allow-Credentials', 'true')
                response.headers.add('Access-Control-Max-Age', '86400')
                return response
    
    # Add CORS headers to all responses
    @app.after_request
    def after_request(response):
        from flask import request
        
        origin = request.headers.get('Origin')
        if origin in allowed_origins:
            response.headers.add('Access-Control-Allow-Origin', origin)
            response.headers.add('Access-Control-Allow-Credentials', 'true')
        
        return response
    
    return app
    

def create_app(config_name=os.getenv('FLASK_ENV','production')):
    
    print("🚀 Creating Flask app...")
    
    # Create Flask app
    app = Flask(__name__)
    configure_cors(app) 
    configure_app(app, config_name)
    
    
    print(f"✅ Flask app created: {type(app)}")
    
    initialize_extensions(app)     
      
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
          
 
    
    print("✅ Flask app fully initialized")
    return app


def configure_app(app, config_name):
    
    try:
        from app.config import get_config
        config = get_config(config_name)
        app.config.from_object(config)
        print(f"✅ Configuration loaded: {config_name}")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        # Set basic defaults
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://app_user:Assistext2025Secure@localhost:5432/assistext_prod')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13')

 

def initialize_extensions(app):
    print("🔧 Initializing extensions...")
    try:
        from app.extensions import db, migrate, jwt
                        
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
    
    try:
        # Import all models in the correct order
        from app.models import (
            User, Subscription, SubscriptionPlan, Message, Client,
            Invoice, InvoiceItem, PaymentMethod, Payment,
            CreditTransaction, BillingSettings, UseageRecord,
            ActivityLog, NotificationLog, MessageTemplate
        )
        print("✅ Models imported successfully")
    except Exception as e:
        print(f"❌ Model import failed: {e}")
        # Continue anyway - some models may be optional


def setup_jwt_handlers(app):
    
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