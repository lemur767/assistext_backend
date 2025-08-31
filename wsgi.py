# wsgi.py - FINAL FIXED VERSION
import os
import sys

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
from dotenv import load_dotenv
load_dotenv()

# Set environment variables if not set
if not os.getenv('FLASK_APP'):
    os.environ['FLASK_APP'] = 'app'
if not os.getenv('FLASK_ENV'):
    os.environ['FLASK_ENV'] = 'production'

try:
    from app import create_app
    
    # Create the Flask application - NO PARAMETERS
    application = create_app()
    app = application
    
    if __name__ == "__main__":
        app.run(debug=False, host='0.0.0.0', port=5000)
        
except Exception as e:
    print(f"Failed to create Flask application: {e}")
    import traceback
    traceback.print_exc()
    raise