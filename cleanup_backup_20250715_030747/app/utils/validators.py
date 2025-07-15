# app/utils/validators.py
from typing import Dict, Any, Optional, List, Union
import re
from datetime import datetime

def validate_json_data(data: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """
    Validate JSON data against a simple schema
    
    Args:
        data: The data to validate
        schema: Schema definition with field requirements
        
    Returns:
        Error message if validation fails, None if successful
    """
    for field, rules in schema.items():
        value = data.get(field)
        
        # Check required fields
        if rules.get('required', False) and (value is None or value == ''):
            return f"Field '{field}' is required"
        
        # Skip validation for optional empty fields
        if value is None or value == '':
            continue
        
        # Type validation
        expected_type = rules.get('type')
        if expected_type:
            if expected_type == 'string' and not isinstance(value, str):
                return f"Field '{field}' must be a string"
            elif expected_type == 'integer' and not isinstance(value, int):
                return f"Field '{field}' must be an integer"
            elif expected_type == 'float' and not isinstance(value, (int, float)):
                return f"Field '{field}' must be a number"
            elif expected_type == 'boolean' and not isinstance(value, bool):
                return f"Field '{field}' must be a boolean"
            elif expected_type == 'list' and not isinstance(value, list):
                return f"Field '{field}' must be a list"
        
        # String length validation
        if isinstance(value, str):
            min_length = rules.get('min_length')
            max_length = rules.get('max_length')
            
            if min_length and len(value) < min_length:
                return f"Field '{field}' must be at least {min_length} characters"
            if max_length and len(value) > max_length:
                return f"Field '{field}' must be no more than {max_length} characters"
        
        # Numeric range validation
        if isinstance(value, (int, float)):
            min_val = rules.get('min')
            max_val = rules.get('max')
            
            if min_val is not None and value < min_val:
                return f"Field '{field}' must be at least {min_val}"
            if max_val is not None and value > max_val:
                return f"Field '{field}' must be no more than {max_val}"
        
        # Enum validation
        allowed_values = rules.get('allowed')
        if allowed_values and value not in allowed_values:
            return f"Field '{field}' must be one of: {', '.join(map(str, allowed_values))}"
        
        # Pattern validation
        pattern = rules.get('pattern')
        if pattern and isinstance(value, str):
            if not re.match(pattern, value):
                return f"Field '{field}' format is invalid"
    
    return None

def validate_phone_number(phone_number: str) -> bool:
    """Validate phone number format"""
    # Basic phone number validation for North American numbers
    pattern = r'^\+1[2-9]\d{2}[2-9]\d{2}\d{4}$'
    return bool(re.match(pattern, phone_number))

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
