# app/__init__.py - Clean Flask app initialization
from flask import Flask
from flask_cors import CORS
from app.config import config
import logging
import os

def create_app(config_name=None):
    """Create Flask application factory"""
    
    # Determine config name
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'development')
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    from app.extensions import db, migrate, jwt, socketio
    
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Initialize CORS
    CORS(app, origins=app.config.get('CORS_ORIGINS'))
    
    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins=app.config.get('CORS_ORIGINS'))
    
    # Configure logging
    configure_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Health check endpoint
    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'AssisText Backend',
            'version': '1.0.0',
            'config': config_name
        }
    
    return app


def register_blueprints(app):
    """Register all Flask blueprints"""
    
    # Import blueprints
    from app.api.auth import auth_bp
    from app.api.signup import signup_bp
    from app.api.webhooks import webhooks_bp
    from app.api.profiles import profiles_bp
    from app.api.messages import messages_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(signup_bp, url_prefix='/api/signup')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    
    # Optional blueprints (register if they exist)
    try:
        from app.api.signalwire import signalwire_bp
        app.register_blueprint(signalwire_bp, url_prefix='/api/signalwire')
    except ImportError:
        pass
    
    try:
        from app.api.clients import clients_bp
        app.register_blueprint(clients_bp, url_prefix='/api/clients')
    except ImportError:
        pass
    
    try:
        from app.api.billing import billing_bp
        app.register_blueprint(billing_bp, url_prefix='/api/billing')
    except ImportError:
        pass


def register_error_handlers(app):
    """Register error handlers"""
    
    from app.extensions import jwt
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token'}, 401
    
    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        return {'message': 'Authorization required'}, 401
    
    # General error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'message': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'message': 'Internal server error'}, 500


def configure_logging(app):
    """Configure application logging"""
    
    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Set up file handler
        file_handler = logging.FileHandler('logs/assistext.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('AssisText startup')