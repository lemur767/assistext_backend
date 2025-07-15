#!/bin/bash

# Update Blueprint Registration
# Fix __init__.py to remove deprecated blueprint references

echo "🔧 Updating blueprint registration..."

# Backup the current __init__.py
cp app/__init__.py app/__init__.py.backup.$(date +%Y%m%d_%H%M%S)

# Create updated __init__.py with clean blueprint registration
cat > app/__init__.py << 'EOF'
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from app.config import config
from app.extensions import db, migrate, jwt
import logging

def create_app(config_name=None):
    """Application factory pattern"""
    
    # Set default config
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    print(f"🚀 Creating Flask app with config: {config_name}")
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Setup logging
    setup_logging(app)
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Import models (after extensions are initialized)
    import_models()
    
    # Setup JWT handlers
    setup_jwt_handlers(app)
    
    # Setup error handlers
    setup_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Add health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0'
        }), 200
    
    print("✅ Flask app created successfully")
    return app

def setup_logging(app):
    """Configure application logging"""
    try:
        if not app.debug:
            logging.basicConfig(level=logging.INFO)
        print("✅ Logging configured")
    except Exception as e:
        print(f"❌ Logging setup failed: {e}")

def initialize_extensions(app):
    """Initialize Flask extensions"""
    print("🔧 Initializing extensions...")
    
    try:
        # CORS
        CORS(app, origins=["http://localhost:3000", "http://localhost:5173"])
        print("✅ CORS initialized")
        
        # Database
        db.init_app(app)
        print("✅ Database initialized")
        
        # Migrations
        migrate.init_app(app, db)
        print("✅ Migrations initialized")
        
        # JWT
        jwt.init_app(app)
        print("✅ JWT initialized")
        
    except Exception as e:
        print(f"❌ Extension initialization failed: {e}")
        raise

def import_models():
    """Import all models to ensure they're registered with SQLAlchemy"""
    try:
        from app.models import (
            User, Message, Client, Subscription, SubscriptionPlan,
            Invoice, InvoiceItem, PaymentMethod, Payment
        )
        print("✅ Models imported successfully")
    except Exception as e:
        print(f"❌ Model imports failed: {e}")

def setup_jwt_handlers(app):
    """Setup JWT error handlers"""
    try:
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
    """Setup application error handlers"""
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
    """Register application blueprints"""
    print("🔧 Registering blueprints...")
    
    # Track registered blueprints to prevent duplicates
    registered_blueprints = set()
    blueprints_registered = 0
    
    # Define blueprints - CLEANED UP VERSION
    blueprint_configs = [
        # Core blueprints (required)
        ('app.api.auth', 'auth_bp', '/api/auth', True),
        ('app.api.billing', 'billing_bp', '/api/billing', True),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire', True),
        
        # Feature blueprints (optional)
        ('app.api.messages', 'messages_bp', '/api/messages', False),
        ('app.api.clients', 'clients_bp', '/api/clients', False),
    ]
    
    for module_name, blueprint_name, url_prefix, is_required in blueprint_configs:
        if blueprint_name in registered_blueprints:
            print(f"⚠️  Blueprint {blueprint_name} already registered, skipping")
            continue
            
        try:
            # Import the module
            module = __import__(module_name, fromlist=[blueprint_name])
            
            # Get the blueprint
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                
                # Register the blueprint
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                registered_blueprints.add(blueprint_name)
                blueprints_registered += 1
                
                print(f"✅ Registered {blueprint_name} at {url_prefix}")
            else:
                message = f"Blueprint {blueprint_name} not found in {module_name}"
                if is_required:
                    print(f"❌ {message} (REQUIRED)")
                    raise ImportError(message)
                else:
                    print(f"⚠️  {message} (optional, skipping)")
                    
        except ImportError as e:
            message = f"Failed to import {module_name}: {e}"
            if is_required:
                print(f"❌ {message} (REQUIRED)")
                raise
            else:
                print(f"⚠️  {message} (optional, skipping)")
        except Exception as e:
            message = f"Error registering {blueprint_name}: {e}"
            if is_required:
                print(f"❌ {message} (REQUIRED)")
                raise
            else:
                print(f"⚠️  {message} (optional, skipping)")
    
    print(f"✅ Successfully registered {blueprints_registered} blueprints")
    
    if blueprints_registered == 0:
        print("⚠️  WARNING: No blueprints were registered!")

# Add datetime import for health check
from datetime import datetime
EOF

echo "✅ Updated app/__init__.py with clean blueprint registration"

# Test the updated configuration
echo "🧪 Testing blueprint registration..."
python3 -c "
import sys
sys.path.append('.')
try:
    from app import create_app
    app = create_app('development')
    print('✅ App creation successful')
    print(f'📋 Registered blueprints: {list(app.blueprints.keys())}')
except Exception as e:
    print(f'❌ App creation failed: {e}')
    import traceback
    traceback.print_exc()
"

echo "✅ Blueprint registration update complete!"
echo "👉 Next: Run consolidate_message_services.sh"
