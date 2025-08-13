from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps
import logging

# Import route blueprints
from .auth import auth_bp
from .users import users_bp
from .messaging import messaging_bp
from .billing import billing_bp
from .signalwire import signalwire_bp
from .webhooks import webhooks_bp
from .admin import admin_bp

def register_blueprints(app):
    """Register all API blueprints"""
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(messaging_bp, url_prefix='/api/messaging')
    app.register_blueprint(billing_bp, url_prefix='/api/billing')
    app.register_blueprint(signalwire_bp, url_prefix='/api/signalwire')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')