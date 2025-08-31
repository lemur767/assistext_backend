# app/core/validators.py
"""
UNIFIED VALIDATION SCHEMAS
Consolidates all request validation with consistent patterns
"""
from marshmallow import Schema, fields, validate, ValidationError, post_load
from datetime import datetime, time
import re


# =============================================================================
# CUSTOM VALIDATORS
# =============================================================================

def validate_phone_number(value):
    """Validate phone number format"""
    if not value:
        return value
    
    # Remove all non-digits
    digits_only = re.sub(r'\D', '', value)
    
    # Must be 10-15 digits
    if len(digits_only) < 10 or len(digits_only) > 15:
        raise ValidationError('Phone number must be 10-15 digits')
    
    return value

def validate_password_strength(value):
    """Validate password strength"""
    if len(value) < 8:
        raise ValidationError('Password must be at least 8 characters long')
    
    if not re.search(r'[A-Za-z]', value):
        raise ValidationError('Password must contain at least one letter')
    
    if not re.search(r'\d', value):
        raise ValidationError('Password must contain at least one number')
    
    return value

def validate_timezone(value):
    """Validate timezone string"""
    import pytz
    if value and value not in pytz.all_timezones:
        raise ValidationError('Invalid timezone')
    return value

def validate_area_code(value):
    """Validate area code format"""
    if not value:
        return value
    
    digits_only = re.sub(r'\D', '', value)
    if len(digits_only) != 3:
        raise ValidationError('Area code must be 3 digits')
    
    return digits_only


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseSchema(Schema):
    """Base schema with common functionality"""
    
    class Meta:
        strict = True
        ordered = True
    
    @post_load
    def strip_whitespace(self, data, **kwargs):
        """Strip whitespace from string fields"""
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
        return data


class PaginationSchema(BaseSchema):
    """Pagination parameters"""
    limit = fields.Integer(missing=50, validate=validate.Range(min=1, max=100))
    offset = fields.Integer(missing=0, validate=validate.Range(min=0))


# =============================================================================
# AUTHENTICATION SCHEMAS
# =============================================================================

class RegisterSchema(BaseSchema):
    """User registration validation"""
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=80),
            validate.Regexp(r'^[a-zA-Z0-9_-]+$', error='Username can only contain letters, numbers, underscore, and dash')
        ]
    )
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate_password_strength)
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(validate=validate.Length(min=1, max=50), allow_none=True)
    last_name = fields.Str(validate=validate.Length(min=1, max=50), allow_none=True)
    personal_phone = fields.Str(validate=validate_phone_number, allow_none=True)
    timezone = fields.Str(validate=validate_timezone, missing='UTC')
    
    # Registration-specific fields
    preferred_country = fields.Str(validate=validate.Length(min=2, max=2), missing='US')
    preferred_region = fields.Str(validate=validate.Length(max=50), allow_none=True)
    preferred_city = fields.Str(validate=validate.Length(max=100), allow_none=True)
    preferred_area_code = fields.Str(validate=validate_area_code, allow_none=True)
    
    @post_load
    def validate_passwords_match(self, data, **kwargs):
        """Ensure passwords match"""
        if data['password'] != data['confirm_password']:
            raise ValidationError('Passwords do not match', 'confirm_password')
        
        # Remove confirm_password from final data
        data.pop('confirm_password', None)
        return data


class LoginSchema(BaseSchema):
    """User login validation"""
    email_or_username = fields.Str(required=True, validate=validate.Length(min=3, max=120))
    password = fields.Str(required=True, validate=validate.Length(min=1))


class RefreshTokenSchema(BaseSchema):
    """Refresh token validation"""
    refresh_token = fields.Str(required=True)


class ChangePasswordSchema(BaseSchema):
    """Change password validation"""
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate_password_strength)
    confirm_new_password = fields.Str(required=True)
    
    @post_load
    def validate_passwords_match(self, data, **kwargs):
        """Ensure new passwords match"""
        if data['new_password'] != data['confirm_new_password']:
            raise ValidationError('New passwords do not match', 'confirm_new_password')
        
        data.pop('confirm_new_password', None)
        return data


# =============================================================================
# USER PROFILE SCHEMAS
# =============================================================================

class ProfileUpdateSchema(BaseSchema):
    """User profile update validation"""
    first_name = fields.Str(validate=validate.Length(min=1, max=50), allow_none=True)
    last_name = fields.Str(validate=validate.Length(min=1, max=50), allow_none=True)
    display_name = fields.Str(validate=validate.Length(max=100), allow_none=True)
    personal_phone = fields.Str(validate=validate_phone_number, allow_none=True)
    timezone = fields.Str(validate=validate_timezone, allow_none=True)


class AISettingsSchema(BaseSchema):
    """AI settings validation"""
    ai_enabled = fields.Boolean(allow_none=True)
    ai_personality = fields.Str(validate=validate.Length(max=1000), allow_none=True)
    ai_response_style = fields.Str(
        validate=validate.OneOf(['professional', 'casual', 'friendly', 'formal']),
        allow_none=True
    )
    ai_language = fields.Str(validate=validate.Length(min=2, max=10), allow_none=True)
    use_emojis = fields.Boolean(allow_none=True)
    casual_language = fields.Boolean(allow_none=True)
    custom_instructions = fields.Str(validate=validate.Length(max=2000), allow_none=True)


class AutoReplySettingsSchema(BaseSchema):
    """Auto-reply settings validation"""
    auto_reply_enabled = fields.Boolean(allow_none=True)
    custom_greeting = fields.Str(validate=validate.Length(max=500), allow_none=True)
    out_of_office_enabled = fields.Boolean(allow_none=True)
    out_of_office_message = fields.Str(validate=validate.Length(max=500), allow_none=True)
    out_of_office_start = fields.DateTime(allow_none=True)
    out_of_office_end = fields.DateTime(allow_none=True)
    
    @post_load
    def validate_out_of_office_dates(self, data, **kwargs):
        """Validate out of office date range"""
        start = data.get('out_of_office_start')
        end = data.get('out_of_office_end')
        
        if start and end and start >= end:
            raise ValidationError('Out of office end time must be after start time', 'out_of_office_end')
        
        return data


class BusinessHoursSchema(BaseSchema):
    """Business hours settings validation"""
    business_hours_enabled = fields.Boolean(allow_none=True)
    business_hours_start = fields.Time(allow_none=True)
    business_hours_end = fields.Time(allow_none=True)
    business_days = fields.Str(
        validate=validate.Regexp(r'^[1-7](,[1-7])*$', error='Business days must be comma-separated numbers 1-7'),
        allow_none=True
    )
    after_hours_message = fields.Str(validate=validate.Length(max=500), allow_none=True)
    
    @post_load
    def validate_business_hours(self, data, **kwargs):
        """Validate business hours range"""
        start = data.get('business_hours_start')
        end = data.get('business_hours_end')
        
        if start and end and start >= end:
            raise ValidationError('Business hours end time must be after start time', 'business_hours_end')
        
        return data


class SecuritySettingsSchema(BaseSchema):
    """Security settings validation"""
    enable_flagged_word_detection = fields.Boolean(allow_none=True)
    custom_flagged_words = fields.Str(validate=validate.Length(max=1000), allow_none=True)


# =============================================================================
# MESSAGING SCHEMAS
# =============================================================================

class SendMessageSchema(BaseSchema):
    """Send SMS message validation"""
    to_number = fields.Str(required=True, validate=validate_phone_number)
    body = fields.Str(required=True, validate=validate.Length(min=1, max=1600))
    client_id = fields.Integer(validate=validate.Range(min=1), allow_none=True)


class IncomingMessageSchema(BaseSchema):
    """Incoming message webhook validation"""
    From = fields.Str(required=True, validate=validate_phone_number)
    To = fields.Str(required=True, validate=validate_phone_number)
    Body = fields.Str(required=True, validate=validate.Length(min=1, max=1600))
    MessageSid = fields.Str(required=True)
    AccountSid = fields.Str(required=True)
    FromCity = fields.Str(allow_none=True)
    FromState = fields.Str(allow_none=True)
    FromCountry = fields.Str(allow_none=True)


class MessageHistorySchema(PaginationSchema):
    """Message history query validation"""
    client_id = fields.Integer(validate=validate.Range(min=1), allow_none=True)
    direction = fields.Str(validate=validate.OneOf(['inbound', 'outbound']), allow_none=True)
    start_date = fields.DateTime(allow_none=True)
    end_date = fields.DateTime(allow_none=True)
    
    @post_load
    def validate_date_range(self, data, **kwargs):
        """Validate date range"""
        start = data.get('start_date')
        end = data.get('end_date')
        
        if start and end and start >= end:
            raise ValidationError('End date must be after start date', 'end_date')
        
        return data


# =============================================================================
# CLIENT MANAGEMENT SCHEMAS
# =============================================================================

class CreateClientSchema(BaseSchema):
    """Create client validation"""
    phone_number = fields.Str(required=True, validate=validate_phone_number)
    name = fields.Str(validate=validate.Length(min=1, max=100), allow_none=True)
    email = fields.Email(allow_none=True)
    notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)
    tags = fields.Str(validate=validate.Length(max=500), allow_none=True)


class UpdateClientSchema(BaseSchema):
    """Update client validation"""
    name = fields.Str(validate=validate.Length(min=1, max=100), allow_none=True)
    email = fields.Email(allow_none=True)
    notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)
    tags = fields.Str(validate=validate.Length(max=500), allow_none=True)
    is_blocked = fields.Boolean(allow_none=True)


class ClientListSchema(PaginationSchema):
    """Client list query validation"""
    search = fields.Str(validate=validate.Length(min=1, max=100), allow_none=True)
    tags = fields.Str(allow_none=True)
    is_blocked = fields.Boolean(allow_none=True)


# =============================================================================
# BILLING SCHEMAS
# =============================================================================

class StartTrialSchema(BaseSchema):
    """Start trial validation"""
    payment_method_id = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    preferred_area_code = fields.Str(validate=validate_area_code, missing='416')
    billing_address = fields.Dict(allow_none=True)


class CreatePaymentMethodSchema(BaseSchema):
    """Create payment method validation"""
    payment_method_id = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    is_default = fields.Boolean(missing=False)


class CreateSubscriptionSchema(BaseSchema):
    """Create subscription validation"""
    plan_id = fields.Integer(required=True, validate=validate.Range(min=1))
    payment_method_id = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    billing_cycle = fields.Str(
        validate=validate.OneOf(['monthly', 'yearly']),
        missing='monthly'
    )


class UsageQuerySchema(BaseSchema):
    """Usage statistics query validation"""
    billing_period = fields.Str(
        validate=validate.Regexp(r'^\d{4}-\d{2}$', error='Billing period must be in YYYY-MM format'),
        allow_none=True
    )
    usage_type = fields.Str(
        validate=validate.OneOf(['sms_sent', 'sms_received', 'voice_minutes']),
        allow_none=True
    )


# =============================================================================
# API KEY SCHEMAS
# =============================================================================

class CreateAPIKeySchema(BaseSchema):
    """Create API key validation"""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    permissions = fields.List(
        fields.Str(validate=validate.OneOf(['read', 'write', 'admin'])),
        missing=['read']
    )
    expires_at = fields.DateTime(allow_none=True)


# =============================================================================
# WEBHOOK SCHEMAS
# =============================================================================

class SignalWireWebhookSchema(BaseSchema):
    """SignalWire webhook validation"""
    MessageSid = fields.Str(required=True)
    AccountSid = fields.Str(required=True)
    From = fields.Str(required=True, validate=validate_phone_number)
    To = fields.Str(required=True, validate=validate_phone_number)
    Body = fields.Str(allow_none=True)
    MessageStatus = fields.Str(allow_none=True)
    ErrorCode = fields.Str(allow_none=True)
    ErrorMessage = fields.Str(allow_none=True)


class StatusWebhookSchema(BaseSchema):
    """Message status webhook validation"""
    MessageSid = fields.Str(required=True)
    MessageStatus = fields.Str(required=True, validate=validate.OneOf([
        'queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed'
    ]))
    ErrorCode = fields.Str(allow_none=True)
    ErrorMessage = fields.Str(allow_none=True)


# =============================================================================
# ADMIN SCHEMAS
# =============================================================================

class AdminUserUpdateSchema(BaseSchema):
    """Admin user update validation"""
    is_active = fields.Boolean(allow_none=True)
    is_admin = fields.Boolean(allow_none=True)
    trial_status = fields.Str(
        validate=validate.OneOf(['pending_payment', 'active', 'expired', 'converted']),
        allow_none=True
    )
    trial_expires_at = fields.DateTime(allow_none=True)


# =============================================================================
# VALIDATION HELPER FUNCTIONS
# =============================================================================

def validate_request_data(schema_class, data=None):
    """Decorator for validating request data"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            try:
                schema = schema_class()
                if data is None:
                    # Use request JSON
                    validated_data = schema.load(request.get_json() or {})
                else:
                    # Use provided data
                    validated_data = schema.load(data)
                
                # Add validated data to kwargs
                kwargs['validated_data'] = validated_data
                return f(*args, **kwargs)
                
            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'details': e.messages,
                    'timestamp': datetime.utcnow().isoformat()
                }), 400
                
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def validate_query_params(schema_class):
    """Decorator for validating query parameters"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            try:
                schema = schema_class()
                validated_params = schema.load(request.args.to_dict())
                
                # Add validated params to kwargs
                kwargs['query_params'] = validated_params
                return f(*args, **kwargs)
                
            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': 'Invalid query parameters',
                    'details': e.messages,
                    'timestamp': datetime.utcnow().isoformat()
                }), 400
                
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator