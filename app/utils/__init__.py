# app/utils/__init__.py
"""
Utilities package for SMS AI Responder
Contains helper functions for external services
"""

# Import SignalWire helpers
try:
    from .signalwire_helpers import (
        get_signalwire_client,
        send_sms,
        validate_signalwire_request,
        get_phone_number_info,
        format_phone_number,
        get_available_phone_numbers,
        purchase_phone_number,
        configure_webhook
    )
    
    SIGNALWIRE_AVAILABLE = True
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"Warning: SignalWire helpers not available: {e}")

# Import Ollama LLM helpers
try:
    from .ollama_helpers import (
        get_ollama_client,
        generate_ai_response,
        chat_completion,
        is_llm_available,
        get_llm_health,
        OllamaClient
    )
    
    OLLAMA_AVAILABLE = True
except ImportError as e:
    OLLAMA_AVAILABLE = False
    print(f"Warning: Ollama helpers not available: {e}")

# Security helpers (if they exist)
try:
    from .security import *
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

# Export all available utilities
__all__ = []

# Add SignalWire exports
if SIGNALWIRE_AVAILABLE:
    __all__.extend([
        'get_signalwire_client',
        'send_sms', 
        'validate_signalwire_request',
        'get_phone_number_info',
        'format_phone_number',
        'get_available_phone_numbers',
        'purchase_phone_number',
        'configure_webhook'
    ])

# Add Ollama exports
if OLLAMA_AVAILABLE:
    __all__.extend([
        'get_ollama_client',
        'generate_ai_response',
        'chat_completion', 
        'is_llm_available',
        'get_llm_health',
        'OllamaClient'
    ])

# Convenience functions that work regardless of backend
def send_message(from_number, to_number, body):
    """
    Send SMS message using available SMS service
    """
    if SIGNALWIRE_AVAILABLE:
        return send_sms(from_number, to_number, body)
    else:
        raise RuntimeError("No SMS service available")

def generate_text_response(prompt, system_prompt=None, **kwargs):
    """
    Generate text response using available LLM service
    """
    if OLLAMA_AVAILABLE:
        return generate_ai_response(prompt, system_prompt, **kwargs)
    else:
        raise RuntimeError("No LLM service available")

def get_service_status():
    """
    Get status of all available services
    """
    status = {
        'signalwire': SIGNALWIRE_AVAILABLE,
        'ollama': OLLAMA_AVAILABLE,
        'security': SECURITY_AVAILABLE
    }
    
    # Test actual connectivity if services are available
    if SIGNALWIRE_AVAILABLE:
        try:
            client = get_signalwire_client()
            # Try a simple operation to test connectivity
            status['signalwire_connected'] = True
        except Exception:
            status['signalwire_connected'] = False
    
    if OLLAMA_AVAILABLE:
        try:
            status['ollama_connected'] = is_llm_available()
            if status['ollama_connected']:
                health = get_llm_health()
                status['ollama_health'] = health
        except Exception:
            status['ollama_connected'] = False
    
    return status

# Add convenience functions to exports
__all__.extend([
    'send_message',
    'generate_text_response', 
    'get_service_status'
])

# Service availability flags
__all__.extend([
    'SIGNALWIRE_AVAILABLE',
    'OLLAMA_AVAILABLE', 
    'SECURITY_AVAILABLE'
])
