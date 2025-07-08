import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import get_config
from app.extensions import db, migrate, jwt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name=None):
    """
    Flask application factory
    UPDATED: Removed profile blueprint, added new profile blueprint for single-user profile
    """
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions
    CORS(app, origins=["http://localhost:3000", "http://localhost:5173"])  # Add your frontend URLs
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Set up JWT handlers
    setup_jwt_handlers(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Set up database
    setup_database(app)
    
    logger.info("Flask app created successfully")
    return app


def setup_jwt_handlers(app):
    """Set up JWT error handlers"""
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired', 'message': 'Please log in again'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token', 'message': 'Please provide a valid token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization required', 'message': 'Please provide an access token'}), 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has been revoked', 'message': 'Please log in again'}), 401
    
    logger.info("JWT handlers configured")


def register_error_handlers(app):
    """Register application error handlers"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify({'error': 'Bad request'}), 400
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({'error': 'Unauthorized'}), 401
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({'error': 'Forbidden'}), 403
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        return jsonify({'error': 'Rate limit exceeded', 'message': 'Too many requests'}), 429


def register_blueprints(app):
    """
    Register application blueprints
    UPDATED: Removed profiles blueprint, added new profile blueprint for single-user profile
    """
    
    # Core authentication routes
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        logger.info("✅ Auth blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import auth blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering auth blueprint: {e}")
    
    
    try:
        from app.api.profile import profile_bp
        app.register_blueprint(profile_bp, url_prefix='/api/profile')
        logger.info("✅ Profile blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import profile blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering profile blueprint: {e}")
    
    
    try:
        from app.api.clients import clients_bp
        app.register_blueprint(clients_bp, url_prefix='/api/clients')
        logger.info("✅ Clients blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import clients blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering clients blueprint: {e}")
    
    # Message management routes (updated to work with user instead of profile)
    try:
        from app.api.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        logger.info("✅ Messages blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import messages blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering messages blueprint: {e}")
    
    # Webhook routes (updated to find user by SignalWire phone number)
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
        logger.info("✅ Webhooks blueprint registered")
    except ImportError as e:
        logger.warning(f"Could not import webhooks blueprint: {e}")
    except Exception as e:
        logger.error(f"Error registering webhooks blueprint: {e}")
    
    # Optional blueprints (register if available)
    optional_blueprints = [
        ('app.api.billing', 'billing_bp', '/api/billing'),
        ('app.api.analytics', 'analytics_bp', '/api/analytics'),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire'),
        ('app.api.ai_settings', 'ai_settings_bp', '/api/ai_settings'),  # If you have separate AI settings endpoints
    ]
    
    for module_name, blueprint_name, url_prefix in optional_blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            logger.info(f"✅ {blueprint_name} registered")
        except ImportError:
            logger.info(f"⚠️  {module_name} not available (optional)")
        except Exception as e:
            logger.warning(f"Error registering {blueprint_name}: {e}")


def setup_database(app):
    """Set up database models and tables"""
    try:
        # Import models to register them with SQLAlchemy
        from app.models import User, Client, Message, FlaggedMessage
        
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            logger.info("Database tables created/verified")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Don't raise here - let the app start even if DB setup fails


# Health check endpoint
def add_health_check(app):
    """Add health check endpoint"""
    
    @app.route('/health')
    def health_check():
        try:
            # Test database connection
            from app.models import User
            User.query.first()
            
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    @app.route('/api/health/blueprints')
    def blueprint_health():
        """Check which blueprints are loaded"""
        loaded_blueprints = list(app.blueprints.keys())
        
        expected_blueprints = ['auth', 'profile', 'clients', 'messages', 'webhooks']
        missing_blueprints = [bp for bp in expected_blueprints if bp not in loaded_blueprints]
        
        status = 'healthy' if not missing_blueprints else 'degraded'
        
        return jsonify({
            'status': status,
            'loaded_blueprints': loaded_blueprints,
            'missing_blueprints': missing_blueprints,
            'total_loaded': len(loaded_blueprints)
        }), 200


# For backwards compatibility with existing deployment scripts
def create_application():
    """Alternative entry point for WSGI servers"""
    return create_app()


# Add health checks if requested
def create_app_with_health_checks(config_name=None):
    """Create app with health check endpoints"""
    app = create_app(config_name)
    add_health_check(app)
    return app


if __name__ == '__main__':
    # For development server
    app = create_app('development')
    add_health_check(app)
    app.run(debug=True, host='0.0.0.0', port=5000)