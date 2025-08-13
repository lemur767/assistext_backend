from app.utils.stripe_client import StripeSubscriptionClient as StripeClient
class LLMClient:
    def __init__(self): pass
    def generate_response(self, message, context=None):
        return {'success': True, 'response': 'Thank you for your message.', 'source': 'fallback'}
class SignalWireClient:
    def __init__(self): pass
    def test_connection(self): return {'success': True}
__all__ = ['StripeClient', 'LLMClient', 'SignalWireClient']
