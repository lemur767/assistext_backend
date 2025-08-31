# app/services/sms_conversation_service.py - FINAL FIXED VERSION
import os
import asyncio
import logging
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from flask import current_app
from sqlalchemy.exc import IntegrityError
import signalwire

try:
    from signalwire.relay.consumer import Consumer
except ImportError:
    Consumer = None

@dataclass
class SMSMessage:
    from_number: str
    to_number: str
    body: str
    message_id: str
    timestamp: datetime
    user_id: Optional[int] = None
    subproject_id: Optional[str] = None

@dataclass
class LLMResponse:
    response_text: str
    confidence: float
    tokens_used: int
    processing_time: float

class SMSConversationService:
    def __init__(self):
        self.signalwire_client = signalwire.RestClient(
            os.getenv('SIGNALWIRE_ACCOUNT_SID'),
            os.getenv('SIGNALWIRE_AUTH_TOKEN'),
            signalwire_space_url=os.getenv('SIGNALWIRE_SPACE_URL')
        )
        
        self.ollama_base_url = os.getenv('OLLAMA_SERVER_URL', 'http://internal-llm-server:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'dolphin-mistral:7b')
        self.ollama_timeout = float(os.getenv('OLLAMA_TIMEOUT', '30.0'))
        
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.ollama_timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self.logger = logging.getLogger(__name__)
        self.relay_consumer = None
    
    def _lazy_imports(self):
        """Lazy import models and db to avoid circular imports"""
        from app.extensions import db
        from app.models import User, Message, SignalWireSubproject, SignalWirePhoneNumber
        return db, User, Message, SignalWireSubproject, SignalWirePhoneNumber
    
    async def handle_incoming_sms_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
            
            sms = self._parse_webhook_sms(webhook_data)
            self.logger.info(f"Incoming SMS from {sms.from_number}: {sms.body[:50]}...")
            
            user = await self._find_user_by_phone_number(sms.to_number)
            if not user:
                return {'success': False, 'error': f'No user found for number {sms.to_number}'}
            
            sms.user_id = user.id
            incoming_message = await self._save_incoming_message(sms, user)
            llm_response = await self._generate_llm_response(sms, user, incoming_message)
            response_result = await self._send_sms_response(sms, llm_response, user)
            await self._save_outgoing_message(sms, llm_response, user, response_result)
            
            return {
                'success': True,
                'message_id': incoming_message.id,
                'response_sent': response_result.get('success', False),
                'tokens_used': llm_response.tokens_used
            }
            
        except Exception as e:
            self.logger.error(f"SMS handling failed: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    # FIXED: Remove User type hint that was causing the error
    async def _generate_llm_response(self, sms: SMSMessage, user: Any, 
                                   incoming_message: Any) -> LLMResponse:
        start_time = datetime.utcnow()
        
        try:
            conversation_history = await self._get_conversation_history(
                user.id, sms.from_number, limit=10
            )
            
            prompt = self._build_llm_prompt(sms, user, conversation_history)
            ollama_response = await self._call_ollama_api(prompt, user.id)
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            response_text = ollama_response.get('response', '').strip()
            response_text = self._clean_response_for_sms(response_text)
            estimated_tokens = ollama_response.get('eval_count', 0) + ollama_response.get('prompt_eval_count', 0)
            
            return LLMResponse(
                response_text=response_text or "I'm having trouble processing your message right now.",
                confidence=0.9,
                tokens_used=estimated_tokens,
                processing_time=processing_time
            )
            
        except Exception as e:
            self.logger.error(f"Ollama LLM generation failed: {str(e)}", exc_info=True)
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return LLMResponse(
                response_text="I'm having trouble right now. Please try again in a moment.",
                confidence=0.0,
                tokens_used=0,
                processing_time=processing_time
            )
    
    async def _call_ollama_api(self, prompt: str, user_id: int) -> Dict[str, Any]:
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 150,
                    "stop": ["\n\n", "User:", "Assistant:", "Human:"]
                }
            }
            
            self.logger.info(f"Calling Ollama at {self.ollama_base_url} for user {user_id}")
            
            response = await self.http_client.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            self.logger.info(f"Ollama response received: {len(result.get('response', ''))} chars, "
                           f"{result.get('eval_count', 0)} tokens")
            
            return result
            
        except httpx.TimeoutException:
            self.logger.error(f"Ollama request timeout after {self.ollama_timeout}s")
            raise Exception("LLM server timeout")
        except httpx.ConnectError:
            self.logger.error(f"Cannot connect to Ollama server at {self.ollama_base_url}")
            raise Exception("LLM server unavailable")
        except Exception as e:
            self.logger.error(f"Ollama API call failed: {str(e)}")
            raise
    
    def _clean_response_for_sms(self, response: str) -> str:
        if not response:
            return ""
        
        response = response.replace("Assistant:", "").replace("AI:", "").strip()
        response = ' '.join(response.split())
        
        if len(response) > 1500:
            response = response[:1500] + "..."
        
        response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')
        return response.strip()
    
    async def _send_sms_response(self, original_sms: SMSMessage, llm_response: LLMResponse, user: Any) -> Dict[str, Any]:
        try:
            user_phone = await self._get_user_signalwire_number(user.id)
            if not user_phone:
                return {'success': False, 'error': 'No phone number configured for user'}
            
            message = self.signalwire_client.messages.create(
                from_=user_phone.phone_number,
                to=original_sms.from_number,
                body=llm_response.response_text[:1600]
            )
            
            self.logger.info(f"Sent SMS response: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'sent_at': datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send SMS response: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def setup_user_signalwire(self, user_id: int) -> Dict[str, Any]:
        try:
            db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
            
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            self.logger.info(f"Setting up SignalWire for user {user_id}")
            
            subproject_result = await self._create_user_subproject(user)
            if not subproject_result['success']:
                return subproject_result
            
            subproject = subproject_result['subproject']
            
            phone_result = await self._purchase_user_phone_number(user, subproject)
            if not phone_result['success']:
                return phone_result
            
            phone_number = phone_result['phone_number']
            
            webhook_result = await self._configure_webhooks(user, subproject, phone_number)
            if not webhook_result['success']:
                return webhook_result
            
            await self._save_user_signalwire_config(user, subproject, phone_number)
            
            return {
                'success': True,
                'subproject_id': subproject['id'],
                'phone_number': phone_number['phone_number'],
                'webhook_url': webhook_result['webhook_url']
            }
            
        except Exception as e:
            self.logger.error(f"SignalWire setup failed for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _create_user_subproject(self, user: Any) -> Dict[str, Any]:
        try:
            subproject_data = {
                'name': f"User_{user.id}_{user.username}",
                'description': f"Subproject for user {user.username}",
                'metadata': {
                    'user_id': str(user.id),
                    'created_by': 'sms_conversation_service'
                }
            }
            
            return {
                'success': True,
                'subproject': {
                    'id': os.getenv('SIGNALWIRE_ACCOUNT_SID'),
                    'name': subproject_data['name'],
                    'auth_token': os.getenv('SIGNALWIRE_AUTH_TOKEN')
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Subproject creation failed: {str(e)}'}
    
    async def _purchase_user_phone_number(self, user: Any, subproject: Dict[str, Any]) -> Dict[str, Any]:
        try:
            area_code = getattr(user, 'preferred_area_code', '555')
            
            available_numbers = self.signalwire_client.available_phone_numbers.local.list(
                area_code=area_code,
                limit=1
            )
            
            if not available_numbers:
                available_numbers = self.signalwire_client.available_phone_numbers.local.list(limit=1)
            
            if not available_numbers:
                return {'success': False, 'error': 'No phone numbers available'}
            
            number_to_purchase = available_numbers[0]
            purchased_number = self.signalwire_client.incoming_phone_numbers.create(
                phone_number=number_to_purchase.phone_number
            )
            
            return {
                'success': True,
                'phone_number': {
                    'sid': purchased_number.sid,
                    'phone_number': purchased_number.phone_number,
                    'subproject_id': subproject['id']
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Phone number purchase failed: {str(e)}'}
    
    async def _configure_webhooks(self, user: Any, subproject: Dict[str, Any], phone_number: Dict[str, Any]) -> Dict[str, Any]:
        try:
            base_url = os.getenv('WEBHOOK_BASE_URL', 'https://your-app.com')
            webhook_url = f"{base_url}/api/sms/webhook/user/{user.id}"
            
            self.signalwire_client.incoming_phone_numbers(phone_number['sid']).update(
                sms_url=webhook_url,
                sms_method='POST',
                status_callback=f"{base_url}/api/sms/status/user/{user.id}",
                status_callback_method='POST'
            )
            
            return {
                'success': True,
                'webhook_url': webhook_url
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Webhook configuration failed: {str(e)}'}
    
    # Database operations with lazy imports
    async def _save_incoming_message(self, sms: SMSMessage, user: Any) -> Any:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        message = Message(
            user_id=user.id,
            from_number=sms.from_number,
            to_number=sms.to_number,
            body=sms.body,
            direction='inbound',
            provider='signalwire',
            provider_message_id=sms.message_id,
            status='received',
            received_at=sms.timestamp
        )
        
        db.session.add(message)
        db.session.commit()
        return message
    
    async def _save_outgoing_message(self, original_sms: SMSMessage, llm_response: LLMResponse, user: Any, send_result: Dict[str, Any]) -> Any:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        message = Message(
            user_id=user.id,
            from_number=original_sms.to_number,
            to_number=original_sms.from_number,
            body=llm_response.response_text,
            direction='outbound',
            provider='signalwire',
            provider_message_id=send_result.get('message_sid'),
            status='sent' if send_result.get('success') else 'failed',
            sent_at=send_result.get('sent_at', datetime.utcnow()),
            tokens_used=llm_response.tokens_used,
            processing_time=llm_response.processing_time
        )
        
        db.session.add(message)
        db.session.commit()
        return message
    
    async def _save_user_signalwire_config(self, user: Any, subproject: Dict[str, Any], phone_number: Dict[str, Any]) -> None:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        sw_subproject = SignalWireSubproject(
            user_id=user.id,
            subproject_id=subproject['id'],
            subproject_name=subproject['name'],
            auth_token=subproject['auth_token'],
            created_at=datetime.utcnow()
        )
        db.session.add(sw_subproject)
        
        sw_phone = SignalWirePhoneNumber(
            user_id=user.id,
            subproject_id=subproject['id'],
            phone_number_sid=phone_number['sid'],
            phone_number=phone_number['phone_number'],
            status='active',
            purchased_at=datetime.utcnow()
        )
        db.session.add(sw_phone)
        
        db.session.commit()
    
    # Utility methods
    def _parse_webhook_sms(self, webhook_data: Dict[str, Any]) -> SMSMessage:
        return SMSMessage(
            from_number=webhook_data.get('From', ''),
            to_number=webhook_data.get('To', ''),
            body=webhook_data.get('Body', ''),
            message_id=webhook_data.get('MessageSid', ''),
            timestamp=datetime.utcnow()
        )
    
    async def _find_user_by_phone_number(self, phone_number: str) -> Optional[Any]:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        sw_phone = SignalWirePhoneNumber.query.filter_by(
            phone_number=phone_number,
            status='active'
        ).first()
        
        if sw_phone:
            return User.query.get(sw_phone.user_id)
        return None
    
    async def _get_user_signalwire_number(self, user_id: int) -> Optional[Any]:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        return SignalWirePhoneNumber.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()
    
    async def _get_conversation_history(self, user_id: int, from_number: str, limit: int = 10) -> List[Any]:
        db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
        
        messages = Message.query.filter_by(user_id=user_id).filter(
            (Message.from_number == from_number) | 
            (Message.to_number == from_number)
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        return list(reversed(messages))
    
    def _build_llm_prompt(self, sms: SMSMessage, user: Any, conversation_history: List[Any]) -> str:
        user_name = user.first_name or user.username or "the user"
        
        context_messages = []
        for msg in conversation_history[-5:]:
            if msg.direction == 'inbound':
                context_messages.append(f"Human: {msg.body}")
            else:
                context_messages.append(f"Assistant: {msg.body}")
        
        conversation_context = "\n".join(context_messages) if context_messages else ""
        
        prompt = f"""You are a helpful AI assistant responding to SMS text messages for {user_name}.

{f"Previous conversation:{chr(10)}{conversation_context}{chr(10)}" if conversation_context else ""}Current message from {sms.from_number}: {sms.body}

Instructions:
- Respond naturally and helpfully in a conversational tone
- Keep responses under 160 characters when possible (this is SMS)
- Be friendly but concise
- Don't mention that this is SMS or text messaging
- Don't use excessive punctuation or emojis
- If asked about your capabilities, explain you're an AI assistant that can help with questions and tasks

Response:"""
        
        return prompt
    
    async def health_check(self) -> Dict[str, Any]:
        checks = {}
        
        try:
            response = await self.http_client.get(f"{self.ollama_base_url}/api/tags", timeout=5.0)
            checks['ollama'] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0,
                'models_available': len(response.json().get('models', [])) if response.status_code == 200 else 0
            }
        except Exception as e:
            checks['ollama'] = {'status': 'unhealthy', 'error': str(e)}
        
        try:
            self.signalwire_client.api.accounts.list(limit=1)
            checks['signalwire'] = {'status': 'healthy', 'account_connected': True}
        except Exception as e:
            checks['signalwire'] = {'status': 'unhealthy', 'error': str(e)}
        
        try:
            db, User, Message, SignalWireSubproject, SignalWirePhoneNumber = self._lazy_imports()
            db.session.execute('SELECT 1')
            checks['database'] = {'status': 'healthy'}
        except Exception as e:
            checks['database'] = {'status': 'unhealthy', 'error': str(e)}
        
        overall_status = 'healthy' if all(check.get('status') == 'healthy' for check in checks.values()) else 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'checks': checks,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def cleanup(self):
        await self.http_client.aclose()

# Flask routes
def register_sms_routes(app):
    sms_service = SMSConversationService()
    
    @app.route('/api/sms/webhook/user/<int:user_id>', methods=['POST'])
    def handle_sms_webhook(user_id):
        from flask import request
        import asyncio
        
        webhook_data = request.get_json() or request.form.to_dict()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(sms_service.handle_incoming_sms_webhook(webhook_data))
        finally:
            loop.close()
        
        return result, 200 if result['success'] else 400
    
    @app.route('/api/sms/setup-user/<int:user_id>', methods=['POST'])
    def setup_user_sms(user_id):
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(sms_service.setup_user_signalwire(user_id))
        finally:
            loop.close()
            
        return result, 200 if result['success'] else 400
    
    @app.route('/api/sms/health', methods=['GET'])
    def sms_health_check():
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            health_status = loop.run_until_complete(sms_service.health_check())
        finally:
            loop.close()
            
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        return health_status, status_code