import os
import re
from flask import request

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    # Remove all non-digit characters
    digits = re.sub(r'[^\d]', '', phone)
    
    # Add +1 for North American numbers if not present
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    
    return phone  # Return as-is if can't format