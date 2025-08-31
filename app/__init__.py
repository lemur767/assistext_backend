# app/__init__.py - CORRECTED VERSION
from flask import Flask
import logging
import os
import sys

# Import extensions first
from app.extensions import db, migrate, jwt, mail, init_redis, get_redis

def create_app():
    """Flask application factory - NO config parameter needed"""
    app = Flask(__name__)
    
    # Simple configuration - no complex imports
    _configure_app(app)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    app.logger.setLevel(logging.INFO)
    
    # Initialize extensions
    _init_extensions(app)
    
    # Only register routes if NOT running migrations
    if not _is_flask_migration():
        _register_blueprints(app)
        _register_sms_routes(app)
    else:
        app.logger.info("Skipping route registration during migration")
    
    app.logger.info("AssisText backend startup complete")
    return app

def _configure_app(app):
    """Configure the Flask app with simple settings"""
    # Basic Flask settings
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database settings
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True
    }
    
    # JWT settings  
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])
    
    # CORS settings
    app.config['CORS_ORIGINS'] = ["*"]  # Change in production
    
    # Other settings
    app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'

def _is_flask_migration():
    """Check if we're running a Flask migration command"""
    return any(arg in sys.argv for arg in ['db', 'migrate', 'upgrade', 'downgrade', 'init', 'revision'])

def _init_extensions(app):
    """Initialize Flask extensions"""
    from flask_cors import CORS
    try:
        db.init_app(app)
        app.logger.info("Database initialized")
        
        migrate.init_app(app, db)
        app.logger.info("Migration initialized")
        
        jwt.init_app(app)
        app.logger.info("JWT initialized")
        
        CORS(app)
        app.logger.info("CORS initialized")
        
    except Exception as e:
        app.logger.error(f"Extension initialization failed: {e}")
        # Don't raise during migrations - let them complete
        if not _is_flask_migration():
            raise

def _register_blueprints(app):
    """Register application blueprints"""
    # Simplified blueprint registration - only register if they exist
    blueprints_to_try = [
        ('app.api.auth', 'auth_bp'),
        ('app.api.users', 'users_bp'), 
        ('app.api.billing', 'billing_bp'),
        ('app.api.webhooks', 'webhooks_bp'),
        ('app.api.messages', 'messages_bp'),
        ('app.api.clients', 'clients_bp'),
        ('app.api.analytics', 'analytics_bp'),
    ]
    
    registered_count = 0
    
    for module_path, blueprint_name in blueprints_to_try:
        try:
            # Try to import the module
            module = __import__(module_path, fromlist=[blueprint_name])
            
            # Check if blueprint exists
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                app.register_blueprint(blueprint)
                registered_count += 1
                app.logger.info(f"Registered blueprint: {blueprint_name}")
            else:
                app.logger.debug(f"Blueprint {blueprint_name} not found in {module_path}")
                
        except ImportError:
            app.logger.debug(f"Could not import {module_path}")
        except Exception as e:
            app.logger.warning(f"Error registering {blueprint_name}: {e}")
    
    app.logger.info(f"Registered {registered_count} blueprints")

def _register_sms_routes(app):
    """Register SMS routes safely after app is fully initialized"""
    try:
        # Only register SMS routes if all dependencies are available
        with app.app_context():
            from app.services.sms_conversation_service import register_sms_routes
            register_sms_routes(app)
            app.logger.info("SMS routes registered successfully")
    except ImportError as e:
        app.logger.warning(f"SMS service not available: {e}")
    except Exception as e:
        app.logger.warning(f"Failed to register SMS routes: {e}")

# Simple health check for testing
def health_check():
    """Simple health check for testing app creation"""
    try:
        app = create_app()
        return True
    except Exception:
        return False