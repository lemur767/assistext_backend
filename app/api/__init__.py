

from flask import Blueprint

# List of all available blueprints with their URL prefixes
BLUEPRINT_CONFIGS = [
    ('auth', '/api/auth'),
    ('messages', '/api/messages'),
    ('webhooks', '/api/webhooks'),
    ('billing', '/api/billing'),
    ('user_profile','api/user/profile')
    ('signalwire', '/api/signalwire'),
]

def get_blueprint_by_name(name):
    """Get a blueprint by its name using lazy import."""
    blueprint_map = {
        'auth': lambda: __import__('app.api.auth', fromlist=['auth_bp']).auth_bp,
        'messages': lambda: __import__('app.api.messages', fromlist=['messages_bp']).messages_bp,
        'webhooks': lambda: __import__('app.api.webhooks', fromlist=['webhooks_bp']).webhooks_bp,
        'billing': lambda: __import__('app.api.billing', fromlist=['billing_bp']).billing_bp,
        'user_profile': lambda: __import__('app.api.user_profile', fromlist=['user_profile_bp']).user_profile_bp,
        'signalwire': lambda: __import__('app.api.signalwire', fromlist=['signalwire_bp']).signalwire_bp
    }
    if name in blueprint_map:
        return blueprint_map[name]()
    return None

def register_blueprints(app):
    """Register all blueprints with the Flask application."""
    for blueprint_name, url_prefix in BLUEPRINT_CONFIGS:
        blueprint = get_blueprint_by_name(blueprint_name)
        if blueprint:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        
    # Log registered blueprints
    app.logger.info(f"Registered {len(BLUEPRINT_CONFIGS)} API blueprints")

__all__ = [
    'BLUEPRINT_CONFIGS',
    'register_blueprints',
    'get_blueprint_by_name',
]