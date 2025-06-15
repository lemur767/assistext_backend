"""
API blueprints package initialization.
This file provides utilities for registering API blueprints.
"""

from flask import Blueprint

# List of all available blueprints with their URL prefixes
BLUEPRINT_CONFIGS = [
    ('auth', '/api/auth'),
    ('profiles', '/api/profiles'),
    ('messages', '/api/messages'),
    ('webhooks', '/api/webhooks'),
    ('clients', '/api/clients'),
    ('billing', '/api/billing'),
    ('text_examples', '/api/text_examples'),
    ('ai_settings', '/api/ai_settings'),
    ('signalwire', '/api/signalwire'),
]

def get_blueprint_by_name(name):
    """Get a blueprint by its name using lazy import."""
    blueprint_map = {
        'auth': lambda: __import__('app.api.auth', fromlist=['auth_bp']).auth_bp,
        'profiles': lambda: __import__('app.api.profiles', fromlist=['profiles_bp']).profiles_bp,
        'messages': lambda: __import__('app.api.messages', fromlist=['messages_bp']).messages_bp,
        'webhooks': lambda: __import__('app.api.webhooks', fromlist=['webhooks_bp']).webhooks_bp,
        'clients': lambda: __import__('app.api.client', fromlist=['clients_bp']).clients_bp,
        'billing': lambda: __import__('app.api.billing', fromlist=['billing_bp']).billing_bp,
        'text_examples': lambda: __import__('app.api.text_examples', fromlist=['text_examples_bp']).text_examples_bp,
        'ai_settings': lambda: __import__('app.api.ai_settings', fromlist=['ai_settings_bp']).ai_settings_bp,
        'twilio': lambda: __import__('app.api.twilio', fromlist=['twilio_bp']).twilio_bp,
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