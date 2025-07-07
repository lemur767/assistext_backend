
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name=None):
    """
    Create and configure the Flask application
    
    Args:
        config_name: Configuration name ('development', 'testing', 'production')
                    If None, uses FLASK_ENV environment variable
    
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Determine configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    logger.info(f"Creating Flask app with config: {config_name}")
    
    try:
        # Import and apply configuration
        from app.config import config
        config_class = config.get(config_name, config['default'])
        app.config.from_object(config_class)
        
        logger.info(f"Configuration loaded: {config_class.__name__}")
        
    except ImportError as e:
        logger.error(f"Failed to import config: {e}")
        # Fallback configuration
        configure_app_fallback(app)
    
    # Initialize extensions
    try:
        from app.extensions import init_extensions
        init_extensions(app)
        logger.info("Extensions initialized successfully")
        
    except ImportError as e:
        logger.error(f"Failed to import extensions: {e}")
        # Initialize extensions individually as fallback
        init_extensions_fallback(app)
    except Exception as e:
        logger.error(f"Extensions initialization failed: {e}")
        init_extensions_fallback(app)
    
    # Enable CORS
    CORS(app, 
         origins=app.config.get('CORS_ORIGINS', [
             'https://assitext.ca', 
             'https://www.assitext.ca',
             'http://localhost:3000',  # Development frontend
             'http://127.0.0.1:3000'   # Alternative development
         ]),
         supports_credentials=True)
    
    # Register basic routes
    register_basic_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register API blueprints (CONSOLIDATED - NO PROFILES)
    register_api_blueprints(app)
    
    # Set up database
    setup_database(app)
    
    # Initialize JWT handlers
    setup_jwt_handlers(app)
    
    logger.info("Flask app created successfully")
    return app

def configure_app_fallback(app):
    """Fallback configuration if config.py is not available"""
    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
        'JWT_SECRET_KEY': os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-in-production'),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///app.db'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_ACCESS_TOKEN_EXPIRES': False,  # Tokens don't expire by default
    })
    logger.info("Using fallback configuration")

def init_extensions_fallback(app):
    """Initialize extensions individually if extensions.py fails"""
    try:
        # Try to initialize database
        from flask_sqlalchemy import SQLAlchemy
        from flask_migrate import Migrate
        
        db = SQLAlchemy(app)
        migrate = Migrate(app, db)
        
        # Try to initialize JWT
        jwt = JWTManager(app)
        
        logger.info("Extensions initialized with fallback method")
        
    except Exception as e:
        logger.error(f"Fallback extension initialization failed: {e}")

def register_basic_routes(app):
    """Register basic application routes"""
    
    @app.route('/')
    def index():
        return jsonify({
            'message': 'SMS AI Responder API',
            'version': '2.0.0',
            'status': 'running',
            'endpoints': {
                'auth': '/api/auth',
                'user_profile': '/api/user/profile',
                'clients': '/api/clients',
                'messages': '/api/messages',
                'health': '/api/health'
            }
        })
    
    @app.route('/api/health')
    def health_check():
        """Health check endpoint"""
        try:
            # Test database connection if available
            from app.extensions import db
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except:
            db_status = 'unavailable'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'timestamp': os.environ.get('timestamp', 'unknown')
        }), 200
    
    @app.route('/api/live')
    def liveness_check():
        """Kubernetes/Docker liveness probe"""
        return jsonify({'status': 'alive'}), 200

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify({'error': 'Validation failed', 'details': error.messages}), 400

def register_api_blueprints(app):
    """Register API blueprints - CONSOLIDATED VERSION"""
    
    # Core authentication endpoints
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        logger.info("✅ Auth blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import auth blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering auth blueprint: {e}")
    
    # User profile management (replaces profiles)
    try:
        from app.api.user_profile import user_profile_bp
        app.register_blueprint(user_profile_bp, url_prefix='/api/user')
        logger.info("✅ User profile blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import user profile blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering user profile blueprint: {e}")
    
    # Client management (updated to use user_id)
    try:
        from app.api.clients import clients_bp
        app.register_blueprint(clients_bp, url_prefix='/api/clients')
        logger.info("✅ Clients blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import clients blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering clients blueprint: {e}")
    
    # Message management (updated to use user_id)
    try:
        from app.api.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        logger.info("✅ Messages blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import messages blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering messages blueprint: {e}")
    
    # Webhook handlers
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
        logger.info("✅ Webhooks blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import webhooks blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering webhooks blueprint: {e}")
    
    # Billing system (optional)
    try:
        from app.api.billing import billing_bp
        app.register_blueprint(billing_bp, url_prefix='/api/billing')
        logger.info("✅ Billing blueprint registered")
    except ImportError as e:
        logger.info(f"⚠️  Billing blueprint not available (optional): {e}")
    except Exception as e:
        logger.warning(f"Error registering billing blueprint: {e}")
    
    # AI Settings management
    try:
        from app.api.ai_settings import ai_settings_bp
        app.register_blueprint(ai_settings_bp, url_prefix='/api/ai')
        logger.info("✅ AI settings blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import AI settings blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering AI settings blueprint: {e}")
    
    # SignalWire integration
    try:
        from app.api.signalwire import signalwire_bp
        app.register_blueprint(signalwire_bp, url_prefix='/api/signalwire')
        logger.info("✅ SignalWire blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import SignalWire blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering SignalWire blueprint: {e}")
    
    # Analytics (optional)
    try:
        from app.api.analytics import analytics_bp
        app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
        logger.info("✅ Analytics blueprint registered")
    except ImportError as e:
        logger.info(f"⚠️  Analytics blueprint not available (optional): {e}")
    except Exception as e:
        logger.warning(f"Error registering analytics blueprint: {e}")

def setup_database(app):
    """Set up database models and tables"""
    try:
        from app.extensions import db
        
        # Import models to register them with SQLAlchemy
        try:
            from app.models.user import User
            from app.models.message import Message, MessageTemplate
            from app.models.client import Client
            logger.info("Core models imported successfully")
            
            # Import optional models
            try:
                from app.models.subscription import Subscription
                from app.models.usage_metrics import UsageMetrics
                logger.info("Optional billing models imported")
            except ImportError:
                logger.info("Billing models not available (optional)")
                
        except ImportError as e:
            logger.warning(f"Could not import some models: {e}")
        
        # Create tables if they don't exist
        with app.app_context():
            db.create_all()
            logger.info("Database tables created/verified")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails

def setup_jwt_handlers(app):
    """Set up JWT error handlers"""
    try:
        from flask_jwt_extended import JWTManager
        
        jwt = JWTManager()
        jwt.init_app(app)
        
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return jsonify({'error': 'Token has expired', 'code': 'TOKEN_EXPIRED'}), 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401
        
        @jwt.unauthorized_loader
        def missing_token_callback(error):
            return jsonify({'error': 'Authorization token required', 'code': 'TOKEN_REQUIRED'}), 401
        
        @jwt.revoked_token_loader
        def revoked_token_callback(jwt_header, jwt_payload):
            return jsonify({'error': 'Token has been revoked', 'code': 'TOKEN_REVOKED'}), 401
        
        logger.info("JWT handlers configured")
        
    except Exception as e:
        logger.error(f"JWT setup failed: {e}")

# For backwards compatibility
def create_application():
    """Alternative entry point"""
    return create_app()

# Import validation error for error handler
try:
    from marshmallow import ValidationError
except ImportError:
    # Define a dummy ValidationError if marshmallow is not available
    class ValidationError(Exception):
        def __init__(self, messages):
            self.messages = messages
            super().__init__(str(messages))