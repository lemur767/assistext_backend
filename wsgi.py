from app import create_app
from app.config import config_map
import os



env = os.environ.get('FLASK_ENV', 'production')
config_class = config_map.get(env, config_map['default'])

application = create_app(config_class)

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)
