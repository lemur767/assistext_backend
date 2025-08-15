
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
from datetime import datetime


def create_app(config_name='production'):
    """
    Create Flask application with consolidated configuration
    
    Args:
        config_name: Configuration environment (development, testing, production)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    _load_configuration(app, config_name)
    
    # Initialize extensions
    _initialize_extensions(app)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Setup error handlers
    _setup_error_handlers(app)
    
    # Setup logging
    _setup_logging(app)
    
    # Setup health checks
    _setup_health_checks(app)
    
    app.logger.info("✅ AssisText Backend initialized successfully")
    
    return app


def _load_configuration(app, config_name):
    """Load application configuration based on actual .env structure"""
    
    # Base configuration using actual environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
    
    # PostgreSQL Database Configuration (using actual variable names)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/sms_ai_dev')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }
    
    # JWT Configuration
    from datetime import timedelta
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    
    # SignalWire Configuration (using actual variable names)
    app.config['SIGNALWIRE_PROJECT_ID'] = os.getenv('SIGNALWIRE_PROJECT_ID')
    app.config['SIGNALWIRE_API_TOKEN'] = os.getenv('SIGNALWIRE_API_TOKEN')
    app.config['SIGNALWIRE_SPACE_URL'] = os.getenv('SIGNALWIRE_SPACE_URL')
    
    # LLM Configuration (using actual variable names)
    app.config['LLM_SERVER_URL'] = os.getenv('LLM_SERVER_URL', 'http://10.0.0.102:8080/v1/chat/completions')
    app.config['LLM_API_KEY'] = os.getenv('LLM_API_KEY', 'local-api-key')
    app.config['LLM_MODEL'] = os.getenv('LLM_MODEL', 'llama2')
    
    # Stripe Configuration (using actual variable names)
    app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')
    app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
    app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Redis Configuration
    app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL', app.config['REDIS_URL'])
    app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND', app.config['REDIS_URL'])
    
    # Application URLs
    app.config['FRONTEND_URL'] = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    app.config['BACKEND_URL'] = os.getenv('BACKEND_URL', 'http://localhost:5000')
    app.config['WEBHOOK_BASE_URL'] = os.getenv('WEBHOOK_BASE_URL', app.config['BACKEND_URL'])
    
    # Security Configuration
    app.config['VERIFY_WEBHOOK_SIGNATURES'] = os.getenv('VERIFY_WEBHOOK_SIGNATURES', 'True').lower() == 'true'
    app.config['WEBHOOK_SECRET'] = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret-key')
    
    # Rate Limiting
    app.config['RATELIMIT_STORAGE_URL'] = app.config['REDIS_URL']
    app.config['RATELIMIT_DEFAULT'] = "1000 per hour"
    
    # Allowed Origins
    allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')
    app.config['ALLOWED_ORIGINS'] = [origin.strip() for origin in allowed_origins]
    
    # Environment-specific configurations
    if config_name == 'development':
        app.config['DEBUG'] = True
        app.config['TESTING'] = False
        app.config['RATELIMIT_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DEV_DATABASE_URL', app.config['SQLALCHEMY_DATABASE_URI'])
        
    elif config_name == 'testing':
        app.config['DEBUG'] = False
        app.config['TESTING'] = True
        app.config['RATELIMIT_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('TEST_DATABASE_URL', 'postgresql://username:password@localhost/sms_ai_test')
        
    elif config_name == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['RATELIMIT_ENABLED'] = True
        
        # Security headers in production
        from flask_talisman import Talisman
        try:
            Talisman(app, force_https=True)
        except ImportError:
            app.logger.warning("Flask-Talisman not installed, skipping security headers")
    
    app.logger.info(f"✅ Configuration loaded for: {config_name}")


def _initialize_extensions(app):
    """Initialize Flask extensions"""
    try:
        # Import extensions
        from app.extensions import db, migrate, jwt, limiter
        
        # Database
        db.init_app(app)
        migrate.init_app(app, db)
        app.logger.info("✅ Database extensions initialized")
        
        # JWT
        jwt.init_app(app)
        app.logger.info("✅ JWT initialized")
        
        # Rate limiting
        if app.config.get('RATELIMIT_ENABLED', True):
            limiter.init_app(app)
            app.logger.info("✅ Rate limiting initialized")
        
        # CORS with actual origins
        CORS(app, 
             origins=app.config['ALLOWED_ORIGINS'] + [
                 "https://assitext.ca",
                 "https://www.assitext.ca",
                 "https://backend.assitext.ca"
             ],
             supports_credentials=True,
             allow_headers=['Content-Type', 'Authorization', 'X-API-Key'],
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        )
        app.logger.info("✅ CORS initialized")
        
        # JWT Error Handlers
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return jsonify({
                'success': False,
                'error': 'Token has expired',
                'timestamp': datetime.utcnow().isoformat()
            }), 401
        
        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return jsonify({
                'success': False,
                'error': 'Invalid token',
                'timestamp': datetime.utcnow().isoformat()
            }), 401
        
        @jwt.unauthorized_loader
        def missing_token_callback(error):
            return jsonify({
                'success': False,
                'error': 'Authorization token required',
                'timestamp': datetime.utcnow().isoformat()
            }), 401
        
        app.logger.info("✅ JWT error handlers configured")
        
    except Exception as e:
        app.logger.error(f"❌ Extension initialization failed: {e}")
        raise


def _register_blueprints(app):
    """Register application blueprints"""
    
    # Define blueprints with their configurations
    blueprint_configs = [
        # Core API blueprints
        ('app.api.auth', 'auth_bp', '/api/auth'),
        ('app.api.messaging', 'messaging_bp', '/api/messaging'),
        ('app.api.billing', 'billing_bp', '/api/billing'),
        ('app.api.clients', 'clients_bp', '/api/clients'),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks'),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire'),
        
        # Admin blueprints
        ('app.api.admin', 'admin_bp', '/api/admin'),
    ]
    
    registered_count = 0
    failed_count = 0
    
    for module_path, blueprint_name, url_prefix in blueprint_configs:
        try:
            # Dynamic import
            module = __import__(module_path, fromlist=[blueprint_name])
            
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                app.logger.info(f"✅ Registered {blueprint_name} at {url_prefix}")
                registered_count += 1
            else:
                app.logger.warning(f"⚠️ Blueprint {blueprint_name} not found in {module_path}")
                failed_count += 1
                
        except ImportError as e:
            app.logger.warning(f"⚠️ Could not import {module_path}: {e}")
            failed_count += 1
        except Exception as e:
            app.logger.error(f"❌ Error registering {blueprint_name}: {e}")
            failed_count += 1
    
    app.logger.info(f"📊 Blueprint registration: {registered_count} successful, {failed_count} failed")


def _setup_error_handlers(app):
    """Setup centralized error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad request',
            'message': 'The request could not be understood by the server',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': 'Authentication required',
            'timestamp': datetime.utcnow().isoformat()
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'message': 'Access denied',
            'timestamp': datetime.utcnow().isoformat()
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Not found',
            'message': 'The requested resource was not found',
            'timestamp': datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            'success': False,
            'error': 'Rate limit exceeded',
            'message': 'Too many requests',
            'timestamp': datetime.utcnow().isoformat()
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f"Unhandled exception: {error}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    app.logger.info("✅ Error handlers configured")


def _setup_logging(app):
    """Setup application logging"""
    
    # Set logging level based on environment
    if app.config.get('DEBUG'):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # File handler for production
    if not app.config.get('DEBUG'):
        try:
            os.makedirs('logs', exist_ok=True)
            file_handler = logging.FileHandler('logs/assistext.log')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
        except Exception as e:
            app.logger.warning(f"Could not setup file logging: {e}")
    
    # Set application logger level
    app.logger.setLevel(log_level)
    app.logger.addHandler(console_handler)
    
    # Configure werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)
    
    app.logger.info("✅ Logging configured")


def _setup_health_checks(app):
    """Setup health check endpoints"""
    
    @app.route('/health')
    def health_check():
        """Application health check"""
        try:
            # Check database connection
            from app.extensions import db
            db.session.execute('SELECT 1')
            database_healthy = True
        except Exception:
            database_healthy = False
        
        # Check SignalWire configuration
        signalwire_configured = all([
            app.config.get('SIGNALWIRE_PROJECT_ID'),
            app.config.get('SIGNALWIRE_API_TOKEN'),
            app.config.get('SIGNALWIRE_SPACE_URL')
        ])
        
        # Check Stripe configuration
        stripe_configured = bool(app.config.get('STRIPE_SECRET_KEY'))
        
        # Check LLM server configuration
        llm_configured = bool(app.config.get('LLM_SERVER_URL'))
        
        # Check Redis connection
        redis_healthy = True
        try:
            import redis
            r = redis.from_url(app.config.get('REDIS_URL', 'redis://localhost:6379/0'))
            r.ping()
        except Exception:
            redis_healthy = False
        
        # Overall health status
        is_healthy = database_healthy and signalwire_configured
        
        return jsonify({
            'success': True,
            'status': 'healthy' if is_healthy else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': os.getenv('FLASK_ENV', 'production'),
            'services': {
                'database': database_healthy,
                'signalwire': signalwire_configured,
                'stripe': stripe_configured,
                'llm_server': llm_configured,
                'redis': redis_healthy
            }
        }), 200 if is_healthy else 503
    
    @app.route('/api/health')
    def api_health():
        """API health check"""
        return jsonify({
            'success': True,
            'service': 'api',
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'endpoints': {
                'authentication': '/api/auth',
                'messaging': '/api/messaging',
                'billing': '/api/billing',
                'webhooks': '/api/webhooks',
                'signalwire': '/api/signalwire'
            }
        })
    
    @app.route('/api/info')
    def api_info():
        """API information"""
        return jsonify({
            'name': 'AssisText Backend API',
            'version': '1.0.0',
            'description': 'AI-powered SMS assistant platform with SignalWire integration',
            'documentation': 'https://docs.assitext.ca',
            'support': 'https://support.assitext.ca',
            'status_page': 'https://status.assitext.ca',
            'features': {
                'signalwire_subprojects': True,
                'stripe_billing': True,
                'ai_responses': True,
                'usage_tracking': True,
                'trial_management': True
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    
    app.logger.info("✅ Health check endpoints configured")










