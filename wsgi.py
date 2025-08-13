import os
from app import create_app

# Create application
config_name = os.getenv('FLASK_ENV', 'production')
application = create_app(config_name)

if __name__ == "__main__":
    application.run()