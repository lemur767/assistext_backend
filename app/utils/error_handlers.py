
from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from marshmallow import ValidationError
import logging

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        """Handle Marshmallow validation errors"""
        current_app.logger.warning(f"Validation error: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'errors': e.messages
        }), 400
    
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(e):
        """Handle database errors"""
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database operation failed'
        }), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        """Handle HTTP errors"""
        return jsonify({
            'success': False,
            'error': e.description,
            'code': e.code
        }), e.code
    
    @app.errorhandler(Exception)
    def handle_generic_error(e):
        """Handle unexpected errors"""
        current_app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500