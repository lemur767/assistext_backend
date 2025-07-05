from flask import Flask
from app.extensions import db, jwt, migrate
from app.config import Config
import logging

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    
    # Import models to register them with SQLAlchemy
    from app.models import User
    
    # Register blueprints (with error handling)
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp)
        print("✅ Auth blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering auth routes: {e}")
    
    try:
        from app.api.profile import profile_bp
        app.register_blueprint(profile_bp)
        print("✅ Profile blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering profile routes: {e}")
    
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp)
        print("✅ Webhooks blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering webhooks blueprint: {e}")
    
    try:
        from app.api.signup import signup_bp
        app.register_blueprint(signup_bp, url_prefix='/api/signup')
        print("✅ Signup blueprint registered")
    except Exception as e:
        print(f"⚠️ Could not import signup blueprint: {e}")
    
    return app
