import re
import phonenumbers
from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type

def normalize_phone_number(phone_number, default_country='US'):
    """
    Normalize a phone number to E.164 format.
    
    Args:
        phone_number: Phone number string to normalize
        default_country: Default country code if not provided
        
    Returns:
        str: Normalized phone number in E.164 format
    """
    if not phone_number:
        return None
    
    try:
        # Parse the phone number
        parsed = phonenumbers.parse(phone_number, default_country)
        
        # Check if it's a valid number
        if phonenumbers.is_valid_number(parsed):
            # Format to E.164
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        else:
            # Try basic normalization if phonenumbers fails
            return basic_normalize_phone(phone_number)
    
    except phonenumbers.NumberParseException:
        # Fallback to basic normalization
        return basic_normalize_phone(phone_number)

def basic_normalize_phone(phone_number):
    """Basic phone number normalization fallback"""
    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', phone_number)
    
    # If it starts with 1 and has 11 digits, it's likely US/Canada
    if len(digits_only) == 11 and digits_only.startswith('1'):
        return f"+{digits_only}"
    
    # If it has 10 digits, assume US/Canada and add +1
    elif len(digits_only) == 10:
        return f"+1{digits_only}"
    
    # Otherwise, add + if not present
    elif not phone_number.startswith('+'):
        return f"+{digits_only}"
    
    return phone_number