# app/services/__init__.py - Fixed Service Architecture
"""
Service Layer - Centralized service management with dependency injection
"""
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Service registry to prevent circular imports
_service_registry: Dict[str, Any] = {}

class ServiceManager:
    """Centralized service management"""
    
    def __init__(self):
        self._services = {}
        self._initialized = False
    
    def register_service(self, name: str, service_class, *args, **kwargs):
        """Register a service class"""
        self._services[name] = {
            'class': service_class,
            'args': args,
            'kwargs': kwargs,
            'instance': None
        }
    
    def get_service(self, name: str):
        """Get service instance (lazy loading)"""
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        service_config = self._services[name]
        if service_config['instance'] is None:
            try:
                service_config['instance'] = service_config['class'](
                    *service_config['args'],
                    **service_config['kwargs']
                )
                logger.info(f"✅ Service '{name}' initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize service '{name}': {e}")
                raise
        
        return service_config['instance']
    
    def initialize_all(self):
        """Initialize all registered services"""
        for name in self._services:
            try:
                self.get_service(name)
            except Exception as e:
                logger.error(f"❌ Failed to initialize service '{name}': {e}")
        self._initialized = True

# Global service manager
service_manager = ServiceManager()

def register_all_services():
    """Register all application services"""
    try:
        # Import service classes (lazy to avoid circular imports)
        from app.services.auth_service import AuthService
        from app.services.user_service import UserService
        from app.services.billing_service import BillingService
        from app.services.signalwire_service import SignalWireService
        from app.services.llm_service import LLMService
        from app.services.message_service import MessageService
        from app.services.notification_service import NotificationService
        from app.services.analytics_service import AnalyticsService
        
        # Register services
        service_manager.register_service('auth', AuthService)
        service_manager.register_service('user', UserService)
        service_manager.register_service('billing', BillingService)
        service_manager.register_service('signalwire', SignalWireService)
        service_manager.register_service('llm', LLMService)
        service_manager.register_service('message', MessageService)
        service_manager.register_service('notification', NotificationService)
        service_manager.register_service('analytics', AnalyticsService)
        
        logger.info("✅ All services registered")
        
    except ImportError as e:
        logger.error(f"❌ Service registration failed: {e}")
        raise

# Service getter functions (public API)
@lru_cache(maxsize=None)
def get_auth_service():
    """Get authentication service"""
    return service_manager.get_service('auth')

@lru_cache(maxsize=None)
def get_user_service():
    """Get user management service"""
    return service_manager.get_service('user')

@lru_cache(maxsize=None)
def get_billing_service():
    """Get billing service"""
    return service_manager.get_service('billing')

@lru_cache(maxsize=None)
def get_signalwire_service():
    """Get SignalWire service"""
    return service_manager.get_service('signalwire')

@lru_cache(maxsize=None)
def get_llm_service():
    """Get LLM service"""
    return service_manager.get_service('llm')

@lru_cache(maxsize=None)
def get_message_service():
    """Get message service"""
    return service_manager.get_service('message')

@lru_cache(maxsize=None)
def get_notification_service():
    """Get notification service"""
    return service_manager.get_service('notification')

@lru_cache(maxsize=None)
def get_analytics_service():
    """Get analytics service"""
    return service_manager.get_service('analytics')

# Initialization function
def initialize_services(app=None):
    """Initialize all services with Flask app context"""
    try:
        register_all_services()
        if app:
            with app.app_context():
                service_manager.initialize_all()
        logger.info("✅ Service layer initialized successfully")
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        raise

# Export the public API
__all__ = [
    'get_auth_service',
    'get_user_service', 
    'get_billing_service',
    'get_signalwire_service',
    'get_llm_service',
    'get_message_service',
    'get_notification_service',
    'get_analytics_service',
    'initialize_services',
    'service_manager'
]