from typing import Dict, Any, Optional
from app.models.user import User
from app.extensions import db
from app.utils.external_clients import SignalWireClient, LLMClient, StripeClient


class IntegrationService:
    """Unified external integrations service"""
    
    # =============================================================================
    # SIGNALWIRE INTEGRATION
    # =============================================================================
    
    @staticmethod
    def setup_signalwire_account(user_id: int, phone_number: str) -> Dict[str, Any]:
        """Setup SignalWire account for user"""
        try:
            user = User.query.get_or_404(user_id)
            signalwire = SignalWireClient()
            
            # Configure webhook for phone number
            webhook_url = f"https://backend.assitext.ca/api/webhooks/sms"
            signalwire.configure_webhook(phone_number, webhook_url)
            
            # Update user record
            user.signalwire_phone_number = phone_number
            user.signalwire_configured = True
            
            db.session.commit()
            
            return {
                'phone_number': phone_number,
                'webhook_configured': True,
                'status': 'active'
            }
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"SignalWire setup failed: {str(e)}")
    
    @staticmethod
    def test_signalwire_connection(user_id: int) -> bool:
        """Test SignalWire connection"""
        try:
            user = User.query.get_or_404(user_id)
            if not user.signalwire_phone_number:
                return False
            
            signalwire = SignalWireClient()
            return signalwire.test_connection()
            
        except Exception:
            return False
    
    # =============================================================================
    # LLM INTEGRATION  
    # =============================================================================
    
    @staticmethod
    def test_llm_connection() -> bool:
        """Test LLM service connection"""
        try:
            llm_client = LLMClient()
            return llm_client.test_connection()
        except Exception:
            return False
    
    # =============================================================================
    # STRIPE INTEGRATION
    # =============================================================================
    
    @staticmethod
    def setup_stripe_customer(user_id: int) -> str:
        """Setup Stripe customer for user"""
        try:
            user = User.query.get_or_404(user_id)
            stripe_client = StripeClient()
            
            customer = stripe_client.create_customer(
                email=user.email,
                name=f"{user.first_name} {user.last_name}"
            )
            
            user.stripe_customer_id = customer.id
            db.session.commit()
            
            return customer.id
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Stripe setup failed: {str(e)}")