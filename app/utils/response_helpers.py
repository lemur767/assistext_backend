from flask import jsonify
from typing import Dict, Any, Optional

def success_response(data: Any = None, message: str = None, status_code: int = 200) -> tuple:
    """Create a standardized success response"""
    response = {'success': True}
    
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    
    return jsonify(response), status_code

def error_response(error: str, status_code: int = 400, details: Dict[str, Any] = None) -> tuple:
    """Create a standardized error response"""
    response = {
        'success': False,
        'error': error
    }
    
    if details:
        response['details'] = details
    
    return jsonify(response), status_code

def validation_error_response(errors: Dict[str, str]) -> tuple:
    """Create a validation error response"""
    return error_response(
        'Validation failed',
        400,
        {'validation_errors': errors}
    )