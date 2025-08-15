# =============================================================================
# run.py
"""
APPLICATION ENTRY POINT - CORRECTED VERSION
"""
import os
from app import create_app

# Create application based on FLASK_ENV
config_name = os.getenv('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')
    debug = config_name == 'development'
    
    app.run(
        host=host,
        port=port,
        debug=debug
    )
