import os
import sys
from app import create_app, socketio

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Determine config based on environment
    config_name = os.environ.get('FLASK_ENV', 'production')
    app = create_app(config_name)
    
    # Create Celery instance for worker
    from celery import Celery
    
    def make_celery(app):
        celery = Celery(
            app.import_name,
            backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
            broker=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        )
        celery.conf.update(app.config)
        
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
        return celery
    
    # Create Celery instance
    celery = make_celery(app)
    
    # Register CLI commands
    try:
        from app import cli
        cli.init_app(app)
    except ImportError as e:
        print(f"Warning: Could not import CLI commands: {e}")
    
    print("✅ AssisText Backend started successfully")
    
except Exception as e:
    print(f"❌ Error starting AssisText Backend: {e}")
    raise

if __name__ == '__main__':
    socketio.run(app, debug=app.config.get('DEBUG', False))
