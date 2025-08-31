# app/__init__.py - WITH EXPLICIT .ENV PATH
from flask import Flask
import logging
import os
import sys
from pathlib import Path

# Load environment variables FIRST with explicit path
from dotenv import load_dotenv

# Get the project root directory (parent of app/)
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"

# Load .env file with explicit path and verbose logging
print(f"Looking for .env file at: {env_file}")
print(f".env file exists: {env_file.exists()}")

if env_file.exists():
    result = load_dotenv(env_file)
    print(f"load_dotenv result: {result}")
    print(f"DATABASE_URL after loading: {bool(os.getenv('DATABASE_URL'))}")
else:
    print("❌ .env file not found!")
    # Try loading from current directory
    result = load_dotenv()
    print(f"Fallback load_dotenv result: {result}")

# Import extensions after loading environment
from app.extensions import db, migrate, jwt, mail, init_redis, get_redis

def create_app():
    """Flask application factory - NO config parameter needed"""
    app = Flask(__name__)
    
    # Debug: Print DATABASE_URL status before configuration
    database_url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL found: {bool(database_url)}")
    
    # Simple configuration
    _configure_app(app)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    app.logger.setLevel(logging.INFO)
    
    # Log the database URL for debugging (without password)
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI')
    if db_url and db_url != 'NOT SET':
        # Hide password for logging
        safe_url = db_url.split('@')[1] if '@' in db_url else db_url
        app.logger.info(f"Database URL configured: ...@{safe_url}")
    else:
        app.logger.error("❌ Database URL NOT SET in Flask config!")
    
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
    # Load DATABASE_URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    # Debug: Print what we found
    print(f"_configure_app: DATABASE_URL = {bool(database_url)}")
    
    if not database_url:
        # Try alternative environment variable names
        database_url = os.environ.get('SQLALCHEMY_DATABASE_URI')
        print(f"Tried SQLALCHEMY_DATABASE_URI: {bool(database_url)}")
    
    if not database_url:
        app.logger.error("❌ DATABASE_URL not found in environment variables!")
        app.logger.error("Available environment variables:")
        for key in sorted(os.environ.keys()):
            if 'DATABASE' in key.upper() or 'DB_' in key.upper():
                app.logger.error(f"  {key}={os.environ.get(key)}")
        
        # Show first few environment variables for debugging
        app.logger.error("All environment variables (first 10):")
        for i, (key, value) in enumerate(sorted(os.environ.items())):
            if i < 10:
                if any(secret in key.upper() for secret in ['PASSWORD', 'SECRET', 'TOKEN']):
                    app.logger.error(f"  {key}=***HIDDEN***")
                else:
                    app.logger.error(f"  {key}={value}")
        
        # Use SQLite as fallback
        database_url = 'sqlite:///fallback_app.db'
        app.logger.warning(f"Using fallback database: {database_url}")
    
    # Basic Flask settings
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database settings
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
        app.logger.info("✅ Database initialized")
        
        migrate.init_app(app, db)
        app.logger.info("✅ Migration initialized")
        
        jwt.init_app(app)
        app.logger.info("✅ JWT initialized")
        
        CORS(app)
        app.logger.info("✅ CORS initialized")
        
    except Exception as e:
        app.logger.error(f"❌ Extension initialization failed: {e}")
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
                app.logger.info(f"✅ Registered blueprint: {blueprint_name}")
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
            app.logger.info("✅ SMS routes registered successfully")
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
