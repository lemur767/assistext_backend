from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.config import config
import logging

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

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
    
    # Register blueprints
    from app.api.auth import auth_bp
    from app.api.profiles import profiles_bp
    from app.api.messages import messages_bp
    from app.api.webhooks import webhooks_bp
    from app.api.health import health_bp
    from app.api.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token'}, 401
    
    # Initialize SignalWire after app context is ready
    @app.before_first_request
    def initialize_integrations():
        """Initialize SignalWire integration"""
        try:
            from app.services.signalwire_service import initialize_signalwire_integration
            result = initialize_signalwire_integration()
            
            if result['success']:
                logger.info("SignalWire integration initialized successfully")
            else:
                logger.error(f"SignalWire initialization failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Integration initialization failed: {str(e)}")
    
    return app
