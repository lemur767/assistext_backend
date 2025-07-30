"""
Unified Integration Service for AssisText
Consolidates SignalWire, Stripe, and LLM integrations into one accessible layer

This service handles all external integrations:
- SignalWire: SMS messaging, phone number management, webhooks
- Stripe: Payment processing, subscriptions, billing  
- LLM: AI response generation using Ollama/Dolphin Mistral
"""

import os
import json
import logging
import requests
import stripe
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal

from flask import current_app, request
from sqlalchemy.exc import SQLAlchemyError

# SignalWire imports
from signalwire.rest import Client as SignalWireClient
from signalwire.rest.api.laml.v1 import RequestValidator

# Database imports
from app.extensions import db
from app.models.user import User
from app.models.billing import Subscription, SubscriptionPlan, PaymentMethod, Payment
from app.models.messaging import Message, Client as MessageClient


class IntegrationService:
    """
    Unified integration service handling all external APIs and services
    
    Features:
    - SignalWire SMS and phone number management
    - Stripe payment processing and billing
    - LLM AI response generation
    - Webhook validation and processing
    - Unified error handling and logging
    """
    
    def __init__(self):
        """Initialize all integration clients"""
        self.logger = logging.getLogger(__name__)
        
        # Initialize all clients
        self._initialize_signalwire()
        self._initialize_stripe()
        self._initialize_llm()
        
        self.logger.info("🔧 Integration service initialized with all clients")
    
    # =============================================================================
    # SIGNALWIRE INTEGRATION
    # =============================================================================
    
    def _initialize_signalwire(self):
        """Initialize SignalWire client and configuration"""
        try:
            # Get SignalWire configuration
            self.signalwire_project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
            self.signalwire_auth_token = os.getenv('SIGNALWIRE_AUTH_TOKEN')  
            self.signalwire_space_url = os.getenv('SIGNALWIRE_SPACE_URL')
            self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'https://yourdomain.com')
            
            # Validate required configuration
            if not all([self.signalwire_project_id, self.signalwire_auth_token, self.signalwire_space_url]):
                self.logger.error("❌ Missing required SignalWire configuration")
                self.signalwire_client = None
                self.signalwire_validator = None
                return
            
            # Initialize SignalWire client
            self.signalwire_client = SignalWireClient(
                self.signalwire_project_id,
                self.signalwire_auth_token,
                signalwire_space_url=self.signalwire_space_url
            )
            
            # Initialize webhook validator
            self.signalwire_validator = RequestValidator(self.signalwire_auth_token)
            
            # Test connection
            if self._test_signalwire_connection():
                self.logger.info("✅ SignalWire client initialized successfully")
            else:
                self.logger.error("❌ SignalWire connection test failed")
                
        except Exception as e:
            self.logger.error(f"❌ SignalWire initialization error: {e}")
            self.signalwire_client = None
            self.signalwire_validator = None
    
    def _test_signalwire_connection(self) -> bool:
        """Test SignalWire API connection"""
        try:
            if not self.signalwire_client:
                return False
            
            account = self.signalwire_client.api.account.fetch()
            self.logger.info(f"✅ Connected to SignalWire account: {account.friendly_name}")
            return True
        except Exception as e:
            self.logger.error(f"❌ SignalWire connection test failed: {e}")
            return False
    
    def send_sms(self, from_number: str, to_number: str, body: str) -> Dict[str, Any]:
        """Send SMS message via SignalWire"""
        try:
            if not self.signalwire_client:
                raise Exception("SignalWire client not initialized")
            
            message = self.signalwire_client.messages.create(
                from_=from_number,
                to=to_number,
                body=body,
                status_callback=f"{self.webhook_base_url}/api/webhooks/status"
            )
            
            self.logger.info(f"✅ SMS sent successfully: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'from_number': message.from_,
                'to_number': message.to,
                'body': message.body,
                'price': message.price,
                'direction': message.direction
            }
            
        except Exception as e:
            self.logger.error(f"❌ SMS send failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_phone_numbers(self, area_code: str = None, region: str = 'US', 
                           number_type: str = 'local', limit: int = 10) -> Dict[str, Any]:
        """Search for available phone numbers"""
        try:
            if not self.signalwire_client:
                raise Exception("SignalWire client not initialized")
            
            # Search for numbers based on type
            if number_type == 'local':
                if area_code:
                    numbers = self.signalwire_client.available_phone_numbers(region).local.list(
                        area_code=area_code,
                        limit=limit,
                        sms_enabled=True
                    )
                else:
                    numbers = self.signalwire_client.available_phone_numbers(region).local.list(
                        limit=limit,
                        sms_enabled=True
                    )
            elif number_type == 'toll_free':
                numbers = self.signalwire_client.available_phone_numbers(region).toll_free.list(
                    limit=limit,
                    sms_enabled=True
                )
            else:
                raise ValueError(f"Unsupported number type: {number_type}")
            
            # Format results
            formatted_numbers = []
            for number in numbers:
                formatted_numbers.append({
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'region': number.region,
                    'locality': getattr(number, 'locality', ''),
                    'capabilities': {
                        'sms': getattr(number.capabilities, 'sms', False),
                        'mms': getattr(number.capabilities, 'mms', False),
                        'voice': getattr(number.capabilities, 'voice', False)
                    }
                })
            
            # Add your fallback number if no results
            if not formatted_numbers:
                formatted_numbers.append({
                    'phone_number': '+1 289 917-1708',
                    'friendly_name': 'AssisText Admin Number',
                    'region': 'CA',
                    'locality': 'Toronto',
                    'capabilities': {'sms': True, 'mms': True, 'voice': True},
                    'is_fallback': True
                })
            
            return {
                'success': True,
                'numbers': formatted_numbers,
                'count': len(formatted_numbers)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Phone number search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'numbers': []
            }
    
    def purchase_phone_number(self, phone_number: str, friendly_name: str = None) -> Dict[str, Any]:
        """Purchase a phone number and configure it"""
        try:
            if not self.signalwire_client:
                raise Exception("SignalWire client not initialized")
            
            # Purchase the number with webhook configuration
            purchased_number = self.signalwire_client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=friendly_name or f"AssisText {phone_number[-4:]}",
                sms_url=f"{self.webhook_base_url}/api/webhooks/sms",
                sms_method='POST',
                voice_url=f"{self.webhook_base_url}/api/webhooks/voice",
                voice_method='POST',
                status_callback=f"{self.webhook_base_url}/api/webhooks/status"
            )
            
            self.logger.info(f"✅ Phone number purchased: {phone_number}")
            
            return {
                'success': True,
                'phone_number': purchased_number.phone_number,
                'sid': purchased_number.sid,
                'friendly_name': purchased_number.friendly_name,
                'sms_url': purchased_number.sms_url,
                'voice_url': purchased_number.voice_url,
                'webhook_configured': True
            }
            
        except Exception as e:
            self.logger.error(f"❌ Phone number purchase failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_signalwire_webhook(self, request_data: str, signature: str, url: str) -> bool:
        """Validate SignalWire webhook signature"""
        try:
            if not self.signalwire_validator:
                # Allow in development mode
                if os.getenv('FLASK_ENV') == 'development':
                    self.logger.warning("⚠️ Webhook validation skipped in development mode")
                    return True
                return False
            
            # Validate using SignalWire's RequestValidator
            is_valid = self.signalwire_validator.validate(url, request_data, signature)
            
            if is_valid:
                self.logger.info("✅ SignalWire webhook signature validated")
            else:
                self.logger.warning("❌ Invalid SignalWire webhook signature")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"❌ Webhook validation error: {e}")
            return False
    
    def get_signalwire_status(self) -> Dict[str, Any]:
        """Get SignalWire service status and configuration"""
        status = {
            'service': 'SignalWire',
            'configured': bool(self.signalwire_client),
            'space_url': self.signalwire_space_url,
            'webhook_base_url': self.webhook_base_url
        }
        
        if self.signalwire_client:
            try:
                account = self.signalwire_client.api.account.fetch()
                phone_numbers = self.signalwire_client.incoming_phone_numbers.list(limit=50)
                
                status.update({
                    'status': 'connected',
                    'account_name': account.friendly_name,
                    'phone_numbers_count': len(phone_numbers),
                    'connection_healthy': True
                })
            except Exception as e:
                status.update({
                    'status': 'error',
                    'error': str(e),
                    'connection_healthy': False
                })
        else:
            status.update({
                'status': 'not_configured',
                'connection_healthy': False
            })
        
        return status
    
    # =============================================================================
    # STRIPE INTEGRATION
    # =============================================================================
    
    def _initialize_stripe(self):
        """Initialize Stripe client and configuration"""
        try:
            # Get Stripe configuration
            self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
            self.stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
            self.stripe_api_version = os.getenv('STRIPE_API_VERSION', '2023-10-16')
            
            if not self.stripe_secret_key:
                self.logger.error("❌ Missing STRIPE_SECRET_KEY")
                self.stripe_configured = False
                return
            
            # Configure Stripe
            stripe.api_key = self.stripe_secret_key
            stripe.api_version = self.stripe_api_version
            
            # Test connection
            if self._test_stripe_connection():
                self.stripe_configured = True
                self.logger.info("✅ Stripe client initialized successfully")
            else:
                self.stripe_configured = False
                self.logger.error("❌ Stripe connection test failed")
                
        except Exception as e:
            self.logger.error(f"❌ Stripe initialization error: {e}")
            self.stripe_configured = False
    
    def _test_stripe_connection(self) -> bool:
        """Test Stripe API connection"""
        try:
            # Simple API call to test connection
            stripe.Customer.list(limit=1)
            return True
        except Exception as e:
            self.logger.error(f"❌ Stripe connection test failed: {e}")
            return False
    
    def create_stripe_customer(self, user: User) -> Dict[str, Any]:
        """Create a Stripe customer for a user"""
        try:
            if not self.stripe_configured:
                raise Exception("Stripe not configured")
            
            if user.stripe_customer_id:
                return {
                    'success': True,
                    'customer_id': user.stripe_customer_id,
                    'already_exists': True
                }
            
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    'user_id': str(user.id),
                    'created_via': 'assistext_app'
                }
            )
            
            # Update user record
            user.stripe_customer_id = customer.id
            db.session.commit()
            
            self.logger.info(f"✅ Created Stripe customer {customer.id} for user {user.id}")
            
            return {
                'success': True,
                'customer_id': customer.id,
                'already_exists': False,
                'customer_created': True
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"❌ Stripe customer creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_subscription(self, user_id: int, plan_id: str, payment_method_id: str = None) -> Dict[str, Any]:
        """Create a Stripe subscription"""
        try:
            if not self.stripe_configured:
                raise Exception("Stripe not configured")
            
            user = User.query.get_or_404(user_id)
            
            # Ensure user has Stripe customer
            customer_result = self.create_stripe_customer(user)
            if not customer_result['success']:
                return customer_result
            
            customer_id = customer_result['customer_id']
            
            # Create subscription
            subscription_data = {
                'customer': customer_id,
                'items': [{'price': plan_id}],
                'metadata': {
                    'user_id': str(user_id),
                    'created_via': 'assistext_app'
                }
            }
            
            if payment_method_id:
                subscription_data['default_payment_method'] = payment_method_id
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            self.logger.info(f"✅ Created Stripe subscription {subscription.id} for user {user_id}")
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start,
                'current_period_end': subscription.current_period_end,
                'customer_id': customer_id
            }
            
        except Exception as e:
            self.logger.error(f"❌ Stripe subscription creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_payment(self, amount: int, currency: str, customer_id: str, 
                       description: str = None) -> Dict[str, Any]:
        """Process a one-time payment"""
        try:
            if not self.stripe_configured:
                raise Exception("Stripe not configured")
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,  # Amount in cents
                currency=currency,
                customer=customer_id,
                description=description or "AssisText service payment",
                metadata={
                    'processed_via': 'assistext_app'
                }
            )
            
            self.logger.info(f"✅ Created payment intent {payment_intent.id} for ${amount/100}")
            
            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status,
                'amount': payment_intent.amount,
                'currency': payment_intent.currency
            }
            
        except Exception as e:
            self.logger.error(f"❌ Payment processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_stripe_webhook(self, payload: str, signature: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate Stripe webhook signature and parse event"""
        try:
            if not self.stripe_webhook_secret:
                self.logger.warning("⚠️ Stripe webhook secret not configured")
                return False, {'error': 'Webhook secret not configured'}
            
            # Validate signature and construct event
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            
            self.logger.info(f"✅ Valid Stripe webhook: {event['type']}")
            
            return True, {
                'event_id': event['id'],
                'event_type': event['type'],
                'data': event['data']
            }
            
        except stripe.error.SignatureVerificationError:
            self.logger.error("❌ Invalid Stripe webhook signature")
            return False, {'error': 'Invalid signature'}
        except Exception as e:
            self.logger.error(f"❌ Stripe webhook validation error: {e}")
            return False, {'error': str(e)}
    
    def get_stripe_status(self) -> Dict[str, Any]:
        """Get Stripe service status and configuration"""
        status = {
            'service': 'Stripe',
            'configured': self.stripe_configured,
            'api_version': self.stripe_api_version,
            'webhook_configured': bool(self.stripe_webhook_secret)
        }
        
        if self.stripe_configured:
            try:
                # Test with a simple API call
                customers = stripe.Customer.list(limit=1)
                status.update({
                    'status': 'connected',
                    'connection_healthy': True,
                    'test_successful': True
                })
            except Exception as e:
                status.update({
                    'status': 'error',
                    'error': str(e),
                    'connection_healthy': False
                })
        else:
            status.update({
                'status': 'not_configured',
                'connection_healthy': False
            })
        
        return status
    
    # =============================================================================
    # LLM INTEGRATION (OLLAMA/DOLPHIN MISTRAL)
    # =============================================================================
    
    def _initialize_llm(self):
        """Initialize LLM client for AI response generation"""
        try:
            # Get LLM configuration
            self.llm_host = os.getenv('LLM_SERVER_IP', '10.0.0.4')
            self.llm_port = os.getenv('LLM_SERVER_PORT', '8080')
            self.llm_base_url = f"http://{self.llm_host}:{self.llm_port}"
            self.llm_model = os.getenv('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
            self.llm_timeout = int(os.getenv('LLM_TIMEOUT', '30'))
            self.llm_max_tokens = int(os.getenv('LLM_MAX_TOKENS', '150'))
            self.llm_temperature = float(os.getenv('LLM_TEMPERATURE', '0.7'))
            
            # Ollama endpoints
            self.llm_generate_endpoint = f"{self.llm_base_url}/api/generate"
            self.llm_chat_endpoint = f"{self.llm_base_url}/api/chat"
            
            # Test connection
            if self._test_llm_connection():
                self.llm_configured = True
                self.logger.info("✅ LLM client initialized successfully")
            else:
                self.llm_configured = False
                self.logger.error("❌ LLM connection test failed")
                
        except Exception as e:
            self.logger.error(f"❌ LLM initialization error: {e}")
            self.llm_configured = False
    
    def _test_llm_connection(self) -> bool:
        """Test LLM server connection"""
        try:
            payload = {
                "model": self.llm_model,
                "prompt": "Hello",
                "stream": False,
                "options": {"num_predict": 10}
            }
            
            response = requests.post(
                self.llm_generate_endpoint,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"✅ LLM server responding at {self.llm_base_url}")
                return True
            else:
                self.logger.error(f"❌ LLM server returned {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ LLM connection test failed: {e}")
            return False
    
    def generate_ai_response(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate AI response using Ollama/Dolphin Mistral"""
        try:
            if not self.llm_configured:
                return self._get_llm_fallback_response("llm_not_configured")
            
            if not message or not message.strip():
                return self._get_llm_fallback_response("empty_message")
            
            # Build prompt for Dolphin Mistral
            system_prompt = self._build_llm_system_prompt(context)
            
            self.logger.info(f"🤖 Generating AI response for: '{message[:50]}...'")
            
            # Try chat endpoint first (preferred)
            response = self._try_llm_chat_endpoint(message, system_prompt)
            if response['success']:
                return response
            
            # Fallback to generate endpoint
            response = self._try_llm_generate_endpoint(message, system_prompt)
            if response['success']:
                return response
            
            # If both fail, return fallback
            return self._get_llm_fallback_response("llm_failed")
            
        except Exception as e:
            self.logger.error(f"❌ LLM response generation failed: {e}")
            return self._get_llm_fallback_response("exception", str(e))
    
    def _try_llm_chat_endpoint(self, message: str, system_prompt: str) -> Dict[str, Any]:
        """Try Ollama's chat endpoint"""
        try:
            payload = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "stream": False,
                "options": {
                    "temperature": self.llm_temperature,
                    "num_predict": self.llm_max_tokens,
                    "stop": ["\n\n", "User:", "Human:", "Assistant:"]
                }
            }
            
            response = requests.post(
                self.llm_chat_endpoint,
                json=payload,
                timeout=self.llm_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'message' in result and 'content' in result['message']:
                    ai_response = result['message']['content'].strip()
                    cleaned_response = self._clean_llm_response(ai_response)
                    
                    self.logger.info(f"✅ LLM chat response: '{cleaned_response[:50]}...'")
                    
                    return {
                        'success': True,
                        'response': cleaned_response,
                        'source': 'ollama_chat',
                        'model': self.llm_model,
                        'endpoint': 'chat'
                    }
            
            return {'success': False, 'error': f"Chat endpoint failed: {response.status_code}"}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _try_llm_generate_endpoint(self, message: str, system_prompt: str) -> Dict[str, Any]:
        """Try Ollama's generate endpoint as fallback"""
        try:
            # Combine system prompt and user message
            full_prompt = f"{system_prompt}\n\nUser: {message}\nAssistant:"
            
            payload = {
                "model": self.llm_model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": self.llm_temperature,
                    "num_predict": self.llm_max_tokens,
                    "stop": ["\n\n", "User:", "Human:"]
                }
            }
            
            response = requests.post(
                self.llm_generate_endpoint,
                json=payload,
                timeout=self.llm_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'response' in result:
                    ai_response = result['response'].strip()
                    cleaned_response = self._clean_llm_response(ai_response)
                    
                    self.logger.info(f"✅ LLM generate response: '{cleaned_response[:50]}...'")
                    
                    return {
                        'success': True,
                        'response': cleaned_response,
                        'source': 'ollama_generate',
                        'model': self.llm_model,
                        'endpoint': 'generate'
                    }
            
            return {'success': False, 'error': f"Generate endpoint failed: {response.status_code}"}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _build_llm_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Build system prompt for Dolphin Mistral"""
        base_prompt = """You are an AI assistant for AssisText, a professional SMS communication service. 

Your role:
- Respond to SMS messages professionally and helpfully
- Keep responses under 160 characters when possible
- Be concise, friendly, and actionable
- Always maintain professional tone

Guidelines:
- Respond directly to the user's question or request
- If you need more information, ask one specific question
- For appointment requests, acknowledge and ask for preferred time
- For service inquiries, provide helpful information
- For complaints, acknowledge and offer resolution steps"""
        
        if context:
            business_name = context.get('business_name', 'AssisText')
            business_type = context.get('business_type', 'service provider')
            personality = context.get('personality', 'professional')
            
            base_prompt += f"\n\nBusiness context:\n- Company: {business_name}\n- Type: {business_type}\n- Tone: {personality}"
            
            if context.get('business_hours'):
                base_prompt += f"\n- Business hours: {context['business_hours']}"
        
        base_prompt += "\n\nRespond naturally and helpfully to the following message:"
        
        return base_prompt
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean and format LLM response for SMS"""
        # Remove common artifacts
        response = response.strip()
        
        # Remove assistant prefixes
        prefixes_to_remove = [
            "Assistant:", "AI:", "Response:", "Reply:", 
            "I would respond:", "My response:", "SMS Response:"
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Remove quotes if the entire response is quoted
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        # Limit length for SMS (160 characters is ideal)
        if len(response) > 320:  # Hard limit
            response = response[:317] + "..."
        
        return response
    
    def _get_llm_fallback_response(self, reason: str, error: str = None) -> Dict[str, Any]:
        """Get fallback response when LLM is unavailable"""
        fallback_responses = {
            'llm_not_configured': "Thank you for your message! I'll get back to you soon.",
            'empty_message': "Hello! How can I help you today?",
            'llm_failed': "Thank you for your message. I'm here to help!",
            'timeout': "I received your message. Please give me a moment to respond.",
            'exception': "Thank you for contacting us. We'll get back to you shortly.",
            'connection_error': "Thank you for your message. I'm processing your request."
        }
        
        response = fallback_responses.get(reason, 
            "Thank you for your message. How can I assist you?")
        
        self.logger.info(f"📋 Using LLM fallback response: {reason}")
        
        return {
            'success': True,
            'response': response,
            'source': 'fallback',
            'reason': reason,
            'error': error
        }
    
    def get_llm_status(self) -> Dict[str, Any]:
        """Get LLM service status and configuration"""
        status = {
            'service': 'LLM (Ollama/Dolphin Mistral)',
            'configured': self.llm_configured,
            'base_url': self.llm_base_url,
            'model': self.llm_model,
            'timeout': self.llm_timeout,
            'max_tokens': self.llm_max_tokens
        }
        
        if self.llm_configured:
            try:
                # Test generation
                test_result = self.generate_ai_response("Hello", {'test_mode': True})
                status.update({
                    'status': 'connected',
                    'connection_healthy': True,
                    'test_successful': test_result['success'],
                    'test_source': test_result.get('source', 'unknown')
                })
            except Exception as e:
                status.update({
                    'status': 'error',
                    'error': str(e),
                    'connection_healthy': False
                })
        else:
            status.update({
                'status': 'not_configured',
                'connection_healthy': False
            })
        
        return status
    
    # =============================================================================
    # UNIFIED SERVICE METHODS
    # =============================================================================
    
    def process_incoming_sms(self, from_number: str, to_number: str, message_body: str, 
                           message_sid: str) -> Dict[str, Any]:
        """
        Complete SMS processing workflow:
        1. Generate AI response using LLM
        2. Send response via SignalWire  
        3. Log the conversation
        """
        try:
            self.logger.info(f"📱 Processing SMS: {from_number} -> {to_number}")
            
            # Generate AI response
            ai_context = {
                'from_number': from_number,
                'to_number': to_number,
                'business_name': 'AssisText',
                'business_type': 'SMS AI service'
            }
            
            ai_result = self.generate_ai_response(message_body, ai_context)
            
            if not ai_result['success']:
                self.logger.error(f"❌ AI response generation failed: {ai_result.get('error')}")
                return {
                    'success': False,
                    'error': 'AI response generation failed',
                    'ai_error': ai_result.get('error')
                }
            
            ai_response = ai_result['response']
            
            # Send response via SignalWire
            sms_result = self.send_sms(
                from_number=to_number,  # Reply from the number they texted
                to_number=from_number,  # Send to the original sender
                body=ai_response
            )
            
            if not sms_result['success']:
                self.logger.error(f"❌ SMS response sending failed: {sms_result.get('error')}")
                return {
                    'success': False,
                    'error': 'SMS sending failed',
                    'sms_error': sms_result.get('error'),
                    'ai_response': ai_response  # Include AI response for debugging
                }
            
            # Log successful processing
            self.logger.info(f"✅ SMS processed successfully: {ai_response[:50]}...")
            
            return {
                'success': True,
                'incoming_message': message_body,
                'ai_response': ai_response,
                'ai_source': ai_result.get('source'),
                'outgoing_message_sid': sms_result['message_sid'],
                'response_status': sms_result['status']
            }
            
        except Exception as e:
            self.logger.error(f"❌ SMS processing error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def setup_user_integrations(self, user_id: int, phone_number: str = None) -> Dict[str, Any]:
        """Setup all integrations for a new user"""
        try:
            user = User.query.get_or_404(user_id)
            results = {}
            
            # Setup Stripe customer
            stripe_result = self.create_stripe_customer(user)
            results['stripe'] = stripe_result
            
            # Setup SignalWire (if phone number provided)
            if phone_number:
                signalwire_result = {
                    'success': True,
                    'phone_number': phone_number,
                    'configured': True,
                    'message': 'Phone number configured for SMS processing'
                }
                
                # Update user record
                user.signalwire_phone_number = phone_number
                user.signalwire_configured = True
                db.session.commit()
            else:
                signalwire_result = {
                    'success': True,
                    'configured': False,
                    'message': 'SignalWire ready, phone number needed'
                }
            
            results['signalwire'] = signalwire_result
            
            # LLM is ready by default (no per-user setup needed)
            results['llm'] = {
                'success': True,
                'configured': self.llm_configured,
                'model': self.llm_model,
                'message': 'AI response generation ready'
            }
            
            self.logger.info(f"✅ User integrations setup completed for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'integrations': results,
                'setup_complete': all(r['success'] for r in results.values())
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"❌ User integration setup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all integrated services"""
        try:
            signalwire_status = self.get_signalwire_status()
            stripe_status = self.get_stripe_status()
            llm_status = self.get_llm_status()
            
            # Overall health assessment
            all_healthy = all([
                signalwire_status.get('connection_healthy', False),
                stripe_status.get('connection_healthy', False),
                llm_status.get('connection_healthy', False)
            ])
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'healthy' if all_healthy else 'degraded',
                'services': {
                    'signalwire': signalwire_status,
                    'stripe': stripe_status,
                    'llm': llm_status
                },
                'integration_service': {
                    'status': 'operational',
                    'version': '1.0.0',
                    'features': [
                        'SMS messaging via SignalWire',
                        'Payment processing via Stripe',
                        'AI responses via Ollama/Dolphin Mistral'
                    ]
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Service status check failed: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }
    
    def run_integration_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive diagnostics on all integrations"""
        diagnostics = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests_run': 0,
            'tests_passed': 0,
            'recommendations': []
        }
        
        # Test SignalWire
        diagnostics['tests_run'] += 1
        if self._test_signalwire_connection():
            diagnostics['tests_passed'] += 1
            diagnostics['signalwire_test'] = 'passed'
        else:
            diagnostics['signalwire_test'] = 'failed'
            diagnostics['recommendations'].append('Check SignalWire credentials and network connectivity')
        
        # Test Stripe
        diagnostics['tests_run'] += 1
        if self._test_stripe_connection():
            diagnostics['tests_passed'] += 1
            diagnostics['stripe_test'] = 'passed'
        else:
            diagnostics['stripe_test'] = 'failed'
            diagnostics['recommendations'].append('Check Stripe API key and account status')
        
        # Test LLM
        diagnostics['tests_run'] += 1
        if self._test_llm_connection():
            diagnostics['tests_passed'] += 1
            diagnostics['llm_test'] = 'passed'
        else:
            diagnostics['llm_test'] = 'failed'
            diagnostics['recommendations'].append('Check LLM server is running and accessible')
        
        # Overall assessment
        diagnostics['success_rate'] = diagnostics['tests_passed'] / diagnostics['tests_run']
        diagnostics['overall_health'] = 'healthy' if diagnostics['success_rate'] >= 0.8 else 'degraded'
        
        return diagnostics


# =============================================================================
# SINGLETON PATTERN FOR INTEGRATION SERVICE
# =============================================================================

_integration_service_instance: Optional[IntegrationService] = None

def get_integration_service() -> IntegrationService:
    """
    Get integration service singleton instance
    This is the main entry point for all external integrations
    """
    global _integration_service_instance
    
    if _integration_service_instance is None:
        _integration_service_instance = IntegrationService()
    
    return _integration_service_instance

def reset_integration_service():
    """Reset integration service instance (useful for testing)"""
    global _integration_service_instance
    _integration_service_instance = None

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def send_sms_message(from_number: str, to_number: str, body: str) -> Dict[str, Any]:
    """Convenience function to send SMS"""
    service = get_integration_service()
    return service.send_sms(from_number, to_number, body)

def generate_ai_response(message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Convenience function to generate AI response"""
    service = get_integration_service()
    return service.generate_ai_response(message, context)

def create_customer_subscription(user_id: int, plan_id: str, payment_method_id: str = None) -> Dict[str, Any]:
    """Convenience function to create subscription"""
    service = get_integration_service()
    return service.create_subscription(user_id, plan_id, payment_method_id)

def process_sms_conversation(from_number: str, to_number: str, message_body: str, message_sid: str) -> Dict[str, Any]:
    """Convenience function for complete SMS processing"""
    service = get_integration_service()
    return service.process_incoming_sms(from_number, to_number, message_body, message_sid)

# =============================================================================
# HEALTH CHECK FUNCTION
# =============================================================================

def check_all_integrations() -> Dict[str, Any]:
    """Quick health check for all integrations"""
    try:
        service = get_integration_service()
        return service.get_all_service_status()
    except Exception as e:
        logging.error(f"Integration health check failed: {e}")
        return {
            'overall_status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }