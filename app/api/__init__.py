# app/api/__init__.py

import logging

logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register all blueprints with the Flask application."""
    
    print(f"🔧 register_blueprints called with app type: {type(app)}")
    print(f"🔧 app has register_blueprint: {hasattr(app, 'register_blueprint')}")
    
    if not hasattr(app, 'register_blueprint'):
        print(f"❌ CRITICAL: app object is not a Flask app! It's: {type(app)}")
        print(f"❌ app object: {app}")
        return 0
    
    blueprints_registered = 0
    
    # Core blueprints (required)
    core_blueprints = [
        ('app.api.auth', 'auth_bp', '/api/auth', True),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks', True),
        ('app.api.billing', 'billing_bp', '/api/billing', True),
        ('app.api.signalwire', 'signalwire_bp', '/api/signalwire', True),
    ]
    
    # Updated blueprints (new structure)
    updated_blueprints = [
        ('app.api.user_profile', 'user_profile_bp', '/api/user/profile', False),
        ('app.api.clients', 'clients_bp', '/api/clients', False),
        ('app.api.messages', 'messages_bp', '/api/messages', False),
    ]
    
    # Register all blueprints
    all_blueprints = core_blueprints + updated_blueprints
    
    for module_name, blueprint_name, url_prefix, is_required in all_blueprints:
        try:
            print(f"🔄 Attempting to register {blueprint_name}...")
            
            # Import the module
            module = __import__(module_name, fromlist=[blueprint_name])
            
            # Get the blueprint object
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                print(f"   ✅ Blueprint {blueprint_name} found: {type(blueprint)}")
                
                # Register the blueprint
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                logger.info(f"✅ {blueprint_name} registered at {url_prefix}")
                blueprints_registered += 1
            else:
                if is_required:
                    logger.error(f"❌ {module_name} found but {blueprint_name} not available")
                else:
                    logger.warning(f"⚠️  {module_name} found but {blueprint_name} not available")
                
        except ImportError as e:
            if is_required:
                logger.error(f"❌ Required blueprint {blueprint_name} could not be imported: {e}")
            else:
                logger.info(f"⚠️  Optional blueprint {blueprint_name} not available: {e}")
                
        except Exception as e:
            if is_required:
                logger.error(f"❌ Error registering required blueprint {blueprint_name}: {e}")
            else:
                logger.warning(f"⚠️  Error registering optional blueprint {blueprint_name}: {e}")
    
    logger.info(f"📊 Total blueprints registered: {blueprints_registered}")
    return blueprints_registered

