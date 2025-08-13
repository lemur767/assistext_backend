# app/__init__.py - Fixed Flask Application Factory
"""
AssisText Flask Application - Production Ready
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

def create_app(config_name='production'):
    """Create Flask application with proper configuration"""
    app = Flask(__name__)
    
    # Load configuration
    _configure_app(app, config_name)
    
    # Initialize extensions
    _initialize_extensions(app)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Setup error handlers
    _setup_error_handlers(app)
    
    # Setup logging
    _setup_logging(app)
    
    # Health check endpoint
    _setup_health_checks(app)
    
    app.logger.info("✅ AssisText Backend initialized successfully")
    return app

def _configure_app(app, config_name):
    """Configure Flask application"""
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 60,
        'pool_pre_ping': True
    }
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    
    # Rate limiting
    app.config['RATELIMIT_STORAGE_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # SignalWire Configuration
    app.config['SIGNALWIRE_PROJECT_ID'] = os.getenv('SIGNALWIRE_PROJECT_ID')
    app.config['SIGNALWIRE_AUTH_TOKEN'] = os.getenv('SIGNALWIRE_AUTH_TOKEN')
    app.config['SIGNALWIRE_SPACE_URL'] = os.getenv('SIGNALWIRE_SPACE_URL')
    
    # LLM Configuration
    app.config['LLM_SERVER_URL'] = os.getenv('LLM_SERVER_URL')
    app.config['LLM_MODEL'] = os.getenv('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    app.config['LLM_TIMEOUT'] = int(os.getenv('LLM_TIMEOUT', 30))

def _initialize_extensions(app):
    """Initialize Flask extensions"""
    try:
        from app.extensions import db, migrate, jwt, limiter
        
        # Database
        db.init_app(app)
        migrate.init_app(app, db)
        
        # JWT
        jwt.init_app(app)
        
        # Rate limiting
        limiter.init_app(app)
        
        # CORS
        CORS(app, origins=[
            "https://assitext.ca", 
          
        ])
        
        app.logger.info("✅ Extensions initialized successfully")
        
    except Exception as e:
        app.logger.error(f"❌ Extension initialization failed: {e}")
        raise

def _register_blueprints(app):
    """Register application blueprints"""
    blueprints = [
        # Core API blueprints
        ('app.api.auth', 'auth_bp', '/api/auth'),
        ('app.api.users', 'users_bp', '/api/users'),
        ('app.api.billing', 'billing_bp', '/api/billing'),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire'),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks'),
        ('app.api.messages', 'messages_bp', '/api/messages'),
        ('app.api.clients', 'clients_bp', '/api/clients'),
        ('app.api.analytics', 'analytics_bp', '/api/analytics'),
    ]
    
    registered_count = 0
    for module_path, blueprint_name, url_prefix in blueprints:
        try:
            module = __import__(module_path, fromlist=[blueprint_name])
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                app.logger.info(f"✅ Registered {blueprint_name} at {url_prefix}")
                registered_count += 1
            else:
                app.logger.warning(f"⚠️ Blueprint {blueprint_name} not found in {module_path}")
        except ImportError as e:
            app.logger.warning(f"⚠️ Could not import {module_path}: {e}")
        except Exception as e:
            app.logger.error(f"❌ Error registering {blueprint_name}: {e}")
    
    app.logger.info(f"📊 Registered {registered_count} blueprints")

def _setup_error_handlers(app):
    """Setup error handlers"""
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': 'The request could not be understood by the server'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'Insufficient permissions'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            'error': 'Rate Limit Exceeded',
            'message': f'Rate limit exceeded: {e.description}'
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500

def _setup_logging(app):
    """Setup application logging"""
    if not app.debug and not app.testing:
        # File logging
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/assistext.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('AssisText backend startup')

def _setup_health_checks(app):
    """Setup health check endpoints"""
    @app.route('/health')
    def health():
        """Basic health check"""
        return jsonify({
            'status': 'healthy',
            'message': 'AssisText Backend is running',
            'version': '1.0.0'
        })
    
    @app.route('/health/detailed')
    def detailed_health():
        """Detailed health check with service status"""
        services = {}
        
        # Check database
        try:
            from app.extensions import db
            db.session.execute('SELECT 1')
            services['database'] = 'healthy'
        except Exception as e:
            services['database'] = f'unhealthy: {str(e)}'
        
        # Check SignalWire
        try:
            from app.services.signalwire_service import test_signalwire_connection
            if test_signalwire_connection():
                services['signalwire'] = 'healthy'
            else:
                services['signalwire'] = 'unhealthy'
        except Exception as e:
            services['signalwire'] = f'unhealthy: {str(e)}'
        
        # Check LLM
        try:
            from app.services.llm_service import test_llm_connection
            if test_llm_connection():
                services['llm'] = 'healthy'
            else:
                services['llm'] = 'unhealthy'
        except Exception as e:
            services['llm'] = f'unhealthy: {str(e)}'
        
        overall_status = 'healthy' if all(
            status == 'healthy' for status in services.values()
        ) else 'degraded'
        
        return jsonify({
            'status': overall_status,
            'services': services,
            'timestamp': request.timestamp if hasattr(request, 'timestamp') else None
        })
    
    @app.route('/api/info')
    def api_info():
        """API information endpoint"""
        return jsonify({
            'name': 'AssisText Backend API',
            'version': '1.0.0',
            'environment': os.getenv('FLASK_ENV', 'production'),
            'endpoints': {
                'auth': '/api/auth',
                'users': '/api/users',
                'billing': '/api/billing',
                'signalwire': '/api/signalwire',
                'webhooks': '/api/webhooks',
                'messages': '/api/messages',
                'clients': '/api/clients',
                'analytics': '/api/analytics'
            },
            'documentation': 'https://docs.assitext.ca'
        })

# Create application instance
app = create_app()