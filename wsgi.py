import os
from app import create_app
from app.config import config_map

# Get environment
env = os.environ.get('FLASK_ENV', 'production')

# Get the config class
config_class = config_map.get(env, config_map['production'])

# Create app with proper config
app = create_app(config_class)
application = app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
