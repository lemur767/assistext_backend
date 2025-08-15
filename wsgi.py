
"""
WSGI ENTRY POINT FOR PRODUCTION - CORRECTED VERSION
"""
import os
from app import create_app

# Create application for WSGI (production)
config_name = os.getenv('FLASK_ENV', 'production')
application = create_app(config_name)

if __name__ == "__main__":
    application.run()