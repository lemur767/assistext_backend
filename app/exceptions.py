class SignalWireError(Exception):
    """Base exception for SignalWire-related errors"""
    pass

class SignalWireAccountError(SignalWireError):
    """Exception for SignalWire account creation/management errors"""
    pass

class SignalWireNumberError(SignalWireError):
    """Exception for phone number-related errors"""
    pass

class SignalWireBillingError(SignalWireError):
    """Exception for billing-related errors"""
    pass

class SignalWireWebhookError(SignalWireError):
    """Exception for webhook validation errors"""
    pass

class MessageHandlingError(Exception):
    """Exception for message processing errors"""
    pass

class AIServiceError(Exception):
    """Exception for AI service integration errors"""
    pass

class LLMServerError(AIServiceError):
    """Exception for air-gapped LLM server errors"""
    pass

class LLMServerTimeoutError(LLMServerError):
    """Exception for LLM server timeout errors"""
    pass

class LLMServerUnavailableError(LLMServerError):
    """Exception when LLM server is completely unavailable"""
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

class RateLimitError(Exception):
    """Exception for rate limiting errors"""
    pass

class ConfigurationError(Exception):
    """Exception for configuration-related errors"""
    pass

class VPCNetworkError(Exception):
    """Exception for VPC network connectivity errors"""
    pass