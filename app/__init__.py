from flask import Flask
from flask_cors import CORS
from app.extensions import db, migrate, jwt, socketio
from app.config import Config
import logging
import os

def create_app(config_class=Config):
    """Create Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Initialize CORS
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['https://assitext.ca:3000']))
    
    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins=app.config.get('CORS_ORIGINS', ['https://assitext.ca:3000']))
    
    # Configure logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = logging.FileHandler('logs/assistext.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('AssisText startup')
    
    # Register blueprints
    from app.api.auth import auth_bp
    from app.api.signup import signup_bp  # Updated signup with SignalWire
    from app.api.webhooks import webhooks_bp  # New webhook handler
    from app.api.signalwire import signalwire_bp
    from app.api.profiles import profiles_bp
    from app.api.messages import messages_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(signup_bp, url_prefix='/api/signup')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(signalwire_bp, url_prefix='/api/signalwire')
    app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    
    # Health check endpoint
    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'AssisText Backend',
            'version': '1.0.0',
            'timestamp': app.config.get('START_TIME', 'unknown')
        }
    
    return app