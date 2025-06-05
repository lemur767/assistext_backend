# app/__init__.py - Clean production version
import os
from flask import Flask
from flask_cors import CORS

def create_app(config_name='development'):
    """Create Flask application"""
    
    # Create Flask instance
    app = Flask(__name__)
    
    # Load configuration
    try:
        from app.config import config
        app.config.from_object(config[config_name])
    except Exception as e:
        # Fallback configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DEV_DATABASE_URL', 'sqlite:///fallback.db')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        print(f"Warning: Using fallback config due to: {e}")
    
    # Initialize CORS
    CORS(app)
    
    # Initialize extensions
    try:
        from app.extensions import db, migrate, jwt, socketio
        
        db.init_app(app)
        migrate.init_app(app, db)
        jwt.init_app(app)
        socketio.init_app(app, cors_allowed_origins="*")
        
        # Initialize Celery if available
        try:
            from app.extensions import init_celery
            init_celery(app)
        except ImportError:
            pass  # Celery is optional
            
    except Exception as e:
        print(f"Warning: Extension initialization failed: {e}")
    
    # Register blueprints
    blueprints = [
        ('app.api.auth', 'auth_bp', '/api/auth'),
        ('app.api.profiles', 'profiles_bp', '/api/profiles'),
        ('app.api.messages', 'messages_bp', '/api/messages'),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks'),
        ('app.api.clients', 'clients_bp', '/api/clients'),
        ('app.api.billing', 'billing_bp', '/api/billing'),
        
    ]
    
    for module_name, blueprint_name, url_prefix in blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        except ImportError:
            # Blueprint not found - that's okay, some might not exist yet
            pass
        except Exception as e:
            print(f"Warning: Failed to register {blueprint_name}: {e}")
    
    # JWT error handlers
    try:
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return {'message': 'Token has expired'}, 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return {'message': 'Invalid token'}, 401
        
        @jwt.unauthorized_loader
        def missing_token_callback(error):
            return {'message': 'Authorization token is required'}, 401
    except Exception:
        pass  # JWT handlers are optional if JWT isn't available
    
    # Add basic health check route
    @app.route('/')
    def health_check():
        return {
            "status": "healthy", 
            "message": "SMS AI Responder Backend is running",
            "config": config_name
        }
    
    return app