"""
Fixed Flask App Initialization
app/__init__.py - Works with updated config and extensions
"""
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS

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
         origins=app.config.get('CORS_ORIGINS', ['https://assitext.ca', 'https://www.assitext.ca']),
         supports_credentials=True)
    
    # Register basic routes
    register_basic_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Create database tables if needed
    with app.app_context():
        setup_database(app)
    
    logger.info(f"Flask app created successfully in {config_name} mode")
    return app

def configure_app_fallback(app):
    """Fallback configuration if config.py import fails"""
    logger.warning("Using fallback configuration")
    
    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'fallback-secret-key'),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 
            'postgresql://app_user:AssisText2025!SecureDB@172.234.219.10:5432/assistext_prod?sslmode=require'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_SECRET_KEY': os.environ.get('JWT_SECRET_KEY', 'fallback-jwt-key'),
        'DEBUG': False,
        'SIGNALWIRE_PROJECT_ID': os.environ.get('SIGNALWIRE_PROJECT_ID'),
        'SIGNALWIRE_API_TOKEN': os.environ.get('SIGNALWIRE_API_TOKEN'),
        'SIGNALWIRE_SPACE_URL': os.environ.get('SIGNALWIRE_SPACE_URL'),
        'LLM_SERVER_URL': os.environ.get('LLM_SERVER_URL', 'http://10.0.0.4:8080'),
        'CELERY_BROKER_URL': os.environ.get('CELERY_BROKER_URL', 
            'redis://AssisText2025!Redis:@172.234.219.10:6379/0'),
        'CELERY_RESULT_BACKEND': os.environ.get('CELERY_RESULT_BACKEND',
            'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    })

def init_extensions_fallback(app):
    """Fallback extension initialization"""
    logger.warning("Using fallback extension initialization")
    
    try:
        from app.extensions import db, jwt
        db.init_app(app)
        jwt.init_app(app)
        logger.info("Basic extensions initialized (db, jwt)")
        
        # Try to initialize other extensions individually
        try:
            from app.extensions import socketio
            socketio.init_app(app, cors_allowed_origins="*")
            logger.info("SocketIO initialized")
        except:
            logger.warning("SocketIO initialization failed")
        
        try:
            from app.extensions import mail
            mail.init_app(app)
            logger.info("Mail initialized")
        except:
            logger.warning("Mail initialization failed")
            
        # Configure JWT error handlers
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return {'message': 'Token has expired'}, 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return {'message': 'Invalid token'}, 401
            
    except ImportError as e:
        logger.error(f"Critical extensions import failed: {e}")
        raise

def register_basic_routes(app):
    """Register basic application routes"""
    
    @app.route('/')
    def index():
        return jsonify({
            'service': 'AssisText Backend',
            'status': 'running',
            'version': '1.0.0'
        })
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            from app.extensions import get_extension_status
            status = get_extension_status()
        except:
            status = {'basic': True}
        
        return jsonify({
            'status': 'healthy',
            'service': 'assistext-backend',
            'extensions': status,
            'config': {
                'debug': app.config.get('DEBUG', False),
                'database_configured': bool(app.config.get('SQLALCHEMY_DATABASE_URI')),
                'signalwire_configured': bool(app.config.get('SIGNALWIRE_PROJECT_ID')),
                'llm_configured': bool(app.config.get('LLM_SERVER_URL'))
            }
        })
    
    @app.route('/api/test')
    def api_test():
        """Simple API test endpoint"""
        return jsonify({
            'message': 'API is working',
            'endpoints': [
                '/health',
                '/api/test',
                '/api/auth/*',
                '/api/signup/*',
                '/api/webhooks/*'
            ]
        })

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

def register_blueprints(app):
    """Register application blueprints"""
    
    # Register authentication routes
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        logger.info("✅ Auth blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import auth routes: {e}")
    except Exception as e:
        logger.error(f"Error registering auth routes: {e}")
    
    # Register signup routes (SignalWire phone number management)
    try:
        from app.api.signup import signup_bp
        app.register_blueprint(signup_bp, url_prefix='/api/signup')
        logger.info("✅ Signup blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import signup routes: {e}")
    except Exception as e:
        logger.error(f"Error registering signup routes: {e}")
    
    # Register webhook routes (SignalWire webhooks)
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
        logger.info("✅ Webhooks blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import webhook routes: {e}")
    except Exception as e:
        logger.error(f"Error registering webhook routes: {e}")
    
    # Register fallback webhooks
    try:
        from app.api.fallback_webhooks import fallback_bp
        app.register_blueprint(fallback_bp, url_prefix='/api/webhooks/fallback')
        logger.info("✅ Fallback webhooks registered")
    except ImportError as e:
        logger.warning(f"Could not import fallback webhooks: {e}")
    except Exception as e:
        logger.error(f"Error registering fallback webhooks: {e}")
    
    # Register other blueprints as they become available
    optional_blueprints = [
        ('app.api.profiles', 'profiles_bp', '/api/profiles'),
        ('app.api.messages', 'messages_bp', '/api/messages'),
        ('app.api.clients', 'clients_bp', '/api/clients'),
        ('app.api.billing', 'billing_bp', '/api/billing')
    ]
    
    for module_name, blueprint_name, url_prefix in optional_blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            logger.info(f"✅ {blueprint_name} registered")
        except ImportError:
            logger.info(f"⚠️  {module_name} not available (optional)")
        except Exception as e:
            logger.warning(f"Error registering {blueprint_name}: {e}")

def setup_database(app):
    """Set up database models and tables"""
    try:
        from app.extensions import db
        
        # Import models to register them
        try:
            from app.models import User  # Import your models
            logger.info("Models imported successfully")
        except ImportError:
            logger.warning("Could not import models")
        
        # Create tables if they don't exist
        db.create_all()
        logger.info("Database tables created/verified")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails
        
# For backwards compatibility
def create_application():
    """Alternative entry point"""
    return create_app()