from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.config import config
import logging
import sys
import atexit
import threading

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

# Global flag to track if initialization has run
_initialization_done = False
_initialization_lock = threading.Lock()

def initialize_signalwire_integration():
    """Initialize SignalWire integration"""
    global _initialization_done
    
    with _initialization_lock:
        if _initialization_done:
            return
        
        logger = logging.getLogger(__name__)
        
        try:
            from app.services.signalwire_service import initialize_signalwire_integration as init_sw
            result = init_sw()
            
            if result['success']:
                logger.info("✅ SignalWire integration initialized successfully")
            else:
                logger.error(f"❌ SignalWire initialization failed: {result.get('error', 'Unknown error')}")
                
        except ImportError as e:
            logger.warning(f"⚠️  Could not import SignalWire service: {e}")
        except Exception as e:
            logger.error(f"❌ Integration initialization failed: {str(e)}")
        finally:
            _initialization_done = True

def create_app(config_name='production'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Initialize extensions with app
    CORS(app, origins=['https://assitext.ca', 'https://www.assitext.ca'])
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register blueprints with error handling
    blueprints_to_register = [
        ('app.api.auth', 'auth_bp', '/api/auth'),
        ('app.api.profiles', 'profiles_bp', '/api/profiles'),
        ('app.api.messages', 'messages_bp', '/api/messages'),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks'),
        ('app.api.health', 'health_bp', '/api'),
        ('app.api.dashboard', 'dashboard_bp', '/api/dashboard'),
    ]
    
    for module_name, blueprint_name, url_prefix in blueprints_to_register:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            logger.info(f"✅ Registered blueprint: {module_name}")
        except ImportError as e:
            logger.warning(f"⚠️  Could not import {module_name}: {e}")
        except AttributeError as e:
            logger.warning(f"⚠️  Could not find {blueprint_name} in {module_name}: {e}")
        except Exception as e:
            logger.error(f"❌ Error registering {module_name}: {e}")
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token'}, 401
    
    # Modern Flask initialization approach
    with app.app_context():
        # Create tables if they don't exist
        try:
            db.create_all()
        except Exception as e:
            logger.warning(f"Could not create tables: {e}")
    
    # Initialize SignalWire on first request (modern approach)
    @app.before_request
    def initialize_on_first_request():
        if not _initialization_done:
            # Run initialization in a separate thread to avoid blocking requests
            threading.Thread(target=initialize_signalwire_integration, daemon=True).start()
    
    # Add a basic health endpoint if health blueprint failed to load
    @app.route('/api/health')
    def basic_health():
        return {'status': 'basic_healthy', 'message': 'AssisText Backend is running'}, 200
    
    # Add startup initialization endpoint for manual trigger
    @app.route('/api/initialize', methods=['POST'])
    def manual_initialize():
        try:
            initialize_signalwire_integration()
            return {'success': True, 'message': 'Initialization completed'}, 200
        except Exception as e:
            return {'success': False, 'error': str(e)}, 500
    
    logger.info("🚀 AssisText Backend application created successfully")
    return app
