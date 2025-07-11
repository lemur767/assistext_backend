"""
Fixed WSGI Entry Point
wsgi.py - Works with updated configuration system
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

try:
    # Import the Flask app
    from app import create_app
    
    # Get environment configuration
    config_name = os.environ.get('FLASK_ENV', 'production')
    
    # Create the application
    app = create_app(config_name)
    
    # This is what Gunicorn will use
    application = app
    
    print(f"✅ WSGI app created successfully with config: {config_name}")
    
except ImportError as e:
    print(f"❌ Failed to import create_app: {e}")
    raise
except Exception as e:
    print(f"❌ Failed to create Flask app: {e}")
    raise

# For development server
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )