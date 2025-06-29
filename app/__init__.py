# app/__init__.py - Complete version with all features restored
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_restful import Api
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()

def create_app(config_name='production'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    if config_name == 'production':
        try:
            app.config.from_object('config.ProductionConfig')
        except ImportError:
            # Fallback configuration if config.py doesn't exist
            configure_app_fallback(app)
    else:
        try:
            app.config.from_object('config.DevelopmentConfig')
        except ImportError:
            configure_app_fallback(app)
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    
    # Enable CORS
    CORS(app, origins=[
        "http://localhost:3000", 
        "http://localhost:3173",
        "https://assitext.ca",
        "https://www.assitext.ca"
    ])
    
    # Initialize rate limiting - PROPERLY SCOPED
    limiter = setup_rate_limiting(app)
    
    # Create API instance
    api = Api(app)
    
    # Register blueprints and routes
    register_routes(app, api, limiter)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Create database tables
    create_database_tables(app)
    
    return app

def configure_app_fallback(app):
    """Fallback configuration when config.py is not available"""
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'postgresql://app_user:Assistext2025Secure@localhost/assistext_prod'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': 10,
            'pool_recycle': 120,
            'pool_pre_ping': True
        },
        
        # JWT Configuration
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production'),
        JWT_ACCESS_TOKEN_EXPIRES=False,  # Set to timedelta in production
        
        # SignalWire Configuration
        SIGNALWIRE_SPACE_URL=os.environ.get('SIGNALWIRE_SPACE_URL'),
        SIGNALWIRE_PROJECT_ID=os.environ.get('SIGNALWIRE_PROJECT_ID'),
        SIGNALWIRE_AUTH_TOKEN=os.environ.get('SIGNALWIRE_AUTH_TOKEN'),
        
        # Redis Configuration
        REDIS_URL=os.environ.get('REDIS_URL', 'redis://:Assistext2025Secure@localhost:6379/0'),
        
        # Mail Configuration
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'localhost'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@assistext.ca'),
        
        # Application
        BASE_URL=os.environ.get('BASE_URL', 'http://localhost:5000')
    )

def setup_rate_limiting(app):
    """Setup rate limiting with proper error handling"""
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=["200 per day", "50 per hour"],
            storage_uri=app.config.get('REDIS_URL', 'memory://')
        )
        print("✅ Rate limiting enabled with Redis backend")
        return limiter
    except Exception as e:
        print(f"⚠️ Redis connection failed, using memory backend: {e}")
        try:
            limiter = Limiter(
                key_func=get_remote_address,
                app=app,
                default_limits=["200 per day", "50 per hour"],
                storage_uri='memory://'
            )
            return limiter
        except Exception as e2:
            print(f"⚠️ Rate limiting disabled due to error: {e2}")
            # Create dummy limiter that doesn't actually limit
            class DummyLimiter:
                def limit(self, *args, **kwargs):
                    def decorator(f):
                        return f
                    return decorator
                def exempt(self, f):
                    return f
            return DummyLimiter()

def register_routes(app, api, limiter):
    """Register all application routes and blueprints"""
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'assistext-backend',
            'version': '1.0.0',
            'environment': app.config.get('ENV', 'production')
        }, 200
    
    # Test endpoint
    @app.route('/api/test')
    def test_endpoint():
        return {
            'message': 'AssisText Backend API is working!',
            'endpoints': [
                '/health',
                '/api/test',
                '/api/auth/register',
                '/api/auth/login',
                '/api/signup/search-numbers',
                '/api/signup/complete-signup'
            ]
        }, 200
    @app.route('/api/webhooks')
    def webooks_endpoint():
        try:
            from app.api.webhooks import webhooks_bp
            app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
            print("✅ Webhooks route registered")
        except ImportError as e:
            print(f"⚠️ Could not import webhook route: {e}")
        except Exception as e:
            print(f"⚠️ Error registering webhook route: {e}")
    # Register authentication routes
    try:
        from app.api.auth import register_auth_routes
        register_auth_routes(api, limiter)
        print("✅ Auth routes registered")
    except ImportError as e:
        print(f"⚠️ Could not import auth routes: {e}")
        # Create basic auth endpoints as fallback
        register_basic_auth_routes(api)
    except Exception as e:
        print(f"⚠️ Error registering auth routes: {e}")
    
    # Register signup blueprint
    try:
        from app.api.signup import signup_bp
        app.register_blueprint(signup_bp, url_prefix='/api/signup')
        print("✅ Signup blueprint registered")
    # Register webhooks blueprint
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
        print("✅ Webhooks blueprint registered")
    except ImportError as e:
        print(f"⚠️ Could not import webhooks blueprint: {e}")
    except Exception as e:
        print(f"⚠️ Error registering webhooks blueprint: {e}")
    except ImportError as e:
        print(f"⚠️ Could not import signup blueprint: {e}")
        # Create basic signup endpoints as fallback
        register_basic_signup_routes(app)
    except Exception as e:
        print(f"⚠️ Error registering signup blueprint: {e}")
    try:
        from app.api.signalwire_test import signalwire_test_bp
        app.register_blueprint(signalwire_test_bp, url_prefix='/api/signalwire')
    except ImportError as e:
        print(f"⚠️ Could not import test blueprint: {e}")
    except Exception as e:
        print(f"⚠️ Error Registering Test Blueprint: {e} ")    
    # Register profile routes
    try:
        from app.api.profiles import profiles_bp
        app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
        print("✅ Profiles blueprint registered")
    except ImportError as e:
        print(f"⚠️ Could not import profiles blueprint: {e}")
    except Exception as e:
        print(f"⚠️ Error registering profiles blueprint: {e}")

def register_basic_auth_routes(api):
    """Fallback basic auth routes if main auth module fails"""
    from flask_restful import Resource
    from flask import request, jsonify
    
    class BasicRegisterAPI(Resource):
        def post(self):
            return {'message': 'Registration endpoint placeholder - check auth module'}, 501
    
    class BasicLoginAPI(Resource):
        def post(self):
            return {'message': 'Login endpoint placeholder - check auth module'}, 501
    
    api.add_resource(BasicRegisterAPI, '/api/auth/register')
    api.add_resource(BasicLoginAPI, '/api/auth/login')

def register_basic_signup_routes(app):
    """Fallback basic signup routes if main signup module fails"""
    
    
    @app.route('/api/signup/complete-signup', methods=['POST'])
    def basic_complete_signup():
        return {
            'error': 'Complete signup not available - check signup module'
        }, 501
    
def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return {
            'error': 'Endpoint not found',
            'message': 'The requested API endpoint does not exist'
        }, 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return {
            'error': 'Method not allowed',
            'message': 'The method is not allowed for the requested URL'
        }, 405
    
    @app.errorhandler(500)
    def internal_error(error):
        return {
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }, 500

def create_database_tables(app):
    """Create database tables with proper error handling"""
    with app.app_context():
        try:
            # Import models to ensure they're registered
            from app.models import User, Profile
            
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
        except ImportError as e:
            print(f"⚠️ Could not import models: {e}")
            # Still try to create basic tables
            try:
                db.create_all()
                print("✅ Basic database tables created")
            except Exception as e2:
                print(f"⚠️ Could not create database tables: {e2}")
        except Exception as e:
            print(f"⚠️ Database error: {e}")

# For development server
if __name__ == '__main__':
    app = create_app('production')
    app.run(debug=True, host='0.0.0.0', port=5000)
