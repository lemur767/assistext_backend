# wsgi.py - No Celery version
import os
from app import create_app
from app.extensions import socketio

# Get config from environment
config_name = os.environ.get('FLASK_CONFIG', 'production')

# Create Flask app
app = create_app(config_name)

if __name__ == '__main__':
    socketio.run(app, debug=app.config['DEBUG'], host='0.0.0.0', port=5000)
