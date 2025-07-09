# app/api/__init__.py

import logging

logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register API blueprints for consolidated one-user-one-profile system"""
    
    registered = 0
    
    # Current API endpoints (post-consolidation)
    blueprints = [
        ('app.api.auth', 'auth_bp', '/api/auth'),
        ('app.api.profile', 'profile_bp', '/api/profile'),  # Single profile, not profiles
        ('app.api.messages', 'messages_bp', '/api/messages'),
        ('app.api.clients', 'clients_bp', '/api/clients'),
        ('app.api.webhooks', 'webhooks_bp', '/api/webhooks'),
        ('app.api.billing', 'billing_bp', '/api/billing'),
    ]
    
    for module_name, blueprint_name, url_prefix in blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            if hasattr(module, blueprint_name):
                blueprint = getattr(module, blueprint_name)
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                logger.info(f"✅ {blueprint_name} registered at {url_prefix}")
                registered += 1
            else:
                logger.warning(f"⚠️  {blueprint_name} not found in {module_name}")
        except ImportError as e:
            logger.warning(f"⚠️  Could not import {blueprint_name}: {e}")
        except Exception as e:
            logger.error(f"❌ Error registering {blueprint_name}: {e}")
    
    logger.info(f"📊 Total blueprints registered: {registered}")
    return registered