# wsgi.py
import os
import sys
import traceback
from app import create_app
from app.extensions import socketio

def create_application():
    """Create Flask application with proper error handling"""
    try:
        # Get config from environment variable or default to development
        config_name = os.environ.get('FLASK_CONFIG', 'production')
        print(f"Creating Flask app with config: {config_name}")
        
        # Create Flask application
        app = create_app(config_name)
        
        if app is None:
            raise RuntimeError("create_app() returned None - check your app factory")
        
        print("✓ Flask app created successfully")
        
        # Test app context
        with app.app_context():
            print("✓ App context working")
            
            # Import models to ensure they're registered
            try:
                print("Importing models...")
                # Import each model individually with error handling
                try:
                    from app.models import user
                    print("  ✓ User model imported")
                except ImportError as e:
                    print(f"  ⚠ User model import failed: {e}")
                
                try:
                    from app.models import profile
                    print("  ✓ Profile model imported")
                except ImportError as e:
                    print(f"  ⚠ Profile model import failed: {e}")
                
                try:
                    from app.models import message
                    print("  ✓ Message model imported")
                except ImportError as e:
                    print(f"  ⚠ Message model import failed: {e}")
                
                try:
                    from app.models import client
                    print("  ✓ Client model imported")
                except ImportError as e:
                    print(f"  ⚠ Client model import failed: {e}")
                
                try:
                    from app.models import subscription
                    print("  ✓ Subscription model imported")
                except ImportError as e:
                    print(f"  ⚠ Subscription model import failed: {e}")
                    
            except Exception as model_error:
                print(f"⚠ Model import error: {model_error}")
                # Don't fail the entire app for model import issues
        
        print("✓ Application initialization complete")
        return app
        
    except Exception as e:
        print(f"❌ Failed to create Flask application: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return None

# Create the Flask application
app = create_application()

# Safety check
if app is None:
    print("❌ Application creation failed. Cannot start server.")
    sys.exit(1)

if __name__ == '__main__':
    print("Starting development server...")
    try:
        # Development server
        socketio.run(
            app, 
            debug=app.config.get('DEBUG', False), 
            host='0.0.0.0', 
            port=5000,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        traceback.print_exc()
        sys.exit(1)