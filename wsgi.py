import os
from app import create_app, socketio

# Determine config based on environment
config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

# Register CLI commands
from app import cli
cli.init_app(app)

if __name__ == '__main__':
    socketio.run(app, debug=app.config['DEBUG'])
