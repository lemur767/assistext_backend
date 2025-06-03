# app/exceptions.py

class TwilioError(Exception):
    """Base exception for Twilio-related errors"""
    pass

class TwilioAccountError(TwilioError):
    """Exception for Twilio account creation/management errors"""
    pass

class TwilioNumberError(TwilioError):
    """Exception for phone number-related errors"""
    pass

class TwilioBillingError(TwilioError):
    """Exception for billing-related errors"""
    pass

class MessageHandlingError(Exception):
    """Exception for message processing errors"""
    pass

class AIServiceError(Exception):
    """Exception for AI service integration errors"""
    pass

class DatabaseError(Exception):
    """Exception for database-related errors"""
    pass

class AuthenticationError(Exception):
    """Exception for authentication-related errors"""
    pass

class ValidationError(Exception):
    """Exception for data validation errors"""
    pass