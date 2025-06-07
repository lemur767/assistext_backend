# wsgi.py
import os
from app import create_app
from app.extensions import socketio

# Create Flask application
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == '__main__':
    socketio.run(app, debug=app.config['DEBUG'])
