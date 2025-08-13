from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from flask import current_app

from app.extensions import db
from app.models import User, Client, Message
from app.services.signalwire_service import SignalWireService
from app.services.usage_service import UsageService
from app.utils.ai_client import get_ai_response


class MessagingService:
    """Complete messaging functionality with AI integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.signalwire_service = SignalWireService()
        self.usage_service = UsageService()
    
    def process_incoming_sms(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming SMS from SignalWire webhook
        """
        try:
            # Extract webhook data
            message_sid = webhook_data.get('MessageSid')
            from_number = webhook_data.get('From')
            to_number = webhook_data.get('To')
            body = webhook_data.get('Body', '').strip()
            
            # Find user by phone number
            user = User.query.filter_by(signalwire_phone_number=to_number).first()
            if not user:
                self.logger.warning(f"No user found for phone number: {to_number}")
                return {'success': False, 'error': 'No user found for this number'}
            
            # Find or create client
            client = self._get_or_create_client(user.id, from_number)
            
            # Store incoming message
            message = Message(
                user_id=user.id,
                client_id=client.id,
                body=body,
                from_number=from_number,
                to_number=to_number,
                direction='inbound',
                signalwire_message_sid=message_sid,
                signalwire_status='received'
            )
            
            db.session.add(message)
            
            # Update client stats
            client.total_messages += 1
            client.last_message_at = datetime.utcnow()
            client.last_message_preview = body[:200]
            client.unread_count += 1
            
            db.session.flush()
            
            # Track usage
            self.usage_service.track_usage(
                user_id=user.id,
                metric_type='sms_received',
                quantity=1,
                resource_id=str(message.id),
                resource_type='message'
            )
            
            # Generate AI response if enabled
            ai_response = None
            if client.ai_enabled and body:
                ai_response = self._generate_ai_response(user, client, body)
                
                if ai_response:
                    # Send AI response
                    response_result = self.send_message(
                        user_id=user.id,
                        recipient_number=from_number,
                        content=ai_response['content'],
                        ai_generated=True,
                        ai_model=ai_response.get('model'),
                        ai_confidence=ai_response.get('confidence')
                    )
                    
                    if response_result['success']:
                        self.logger.info(f"AI response sent to {from_number}")
            
            db.session.commit()
            
            return {
                'success': True,
                'message_id': message.id,
                'ai_response_sent': ai_response is not None
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Incoming SMS processing error: {str(e)}")
            return {'success': False, 'error': 'Failed to process incoming SMS'}
    
    def send_message(self, user_id: int, recipient_number: str, content: str, 
                    ai_generated: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Send SMS message via SignalWire
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if not user.signalwire_phone_number:
                return {'success': False, 'error': 'No phone number assigned'}
            
            # Check usage limits
            if not self.usage_service.check_usage_limit(user_id, 'sms_sent'):
                return {'success': False, 'error': 'SMS limit exceeded'}
            
            # Find or create client
            client = self._get_or_create_client(user_id, recipient_number)
            
            # Send via SignalWire
            send_result = self.signalwire_service.send_sms(
                from_number=user.signalwire_phone_number,
                to_number=recipient_number,
                body=content
            )
            
            if not send_result['success']:
                return send_result
            
            # Store outbound message
            message = Message(
                user_id=user_id,
                client_id=client.id,
                body=content,
                from_number=user.signalwire_phone_number,
                to_number=recipient_number,
                direction='outbound',
                ai_generated=ai_generated,
                ai_model=kwargs.get('ai_model'),
                ai_confidence_score=kwargs.get('ai_confidence'),
                signalwire_message_sid=send_result['message_sid'],
                signalwire_status='sent',
                sent_at=datetime.utcnow()
            )
            
            db.session.add(message)
            
            # Update client stats
            client.total_messages += 1
            client.last_message_at = datetime.utcnow()
            client.last_message_preview = content[:200]
            
            # Track usage
            self.usage_service.track_usage(
                user_id=user_id,
                metric_type='sms_sent',
                quantity=1,
                resource_id=str(message.id),
                resource_type='message'
            )
            
            if ai_generated:
                self.usage_service.track_usage(
                    user_id=user_id,
                    metric_type='ai_response',
                    quantity=1,
                    resource_id=str(message.id),
                    resource_type='ai_response'
                )
            
            db.session.commit()
            
            return {
                'success': True,
                'message': message.to_dict(),
                'signalwire_sid': send_result['message_sid']
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Send message error: {str(e)}")
            return {'success': False, 'error': 'Failed to send message'}
    
    def get_conversations(self, user_id: int, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        Get conversation list for user
        """
        try:
            # Get clients with pagination, ordered by last message
            clients_query = Client.query.filter_by(user_id=user_id)\
                .order_by(desc(Client.last_message_at))
            
            clients = clients_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            conversations = []
            for client in clients.items:
                conversation_data = client.to_dict(include_stats=True)
                
                # Get latest message
                latest_message = Message.query.filter_by(client_id=client.id)\
                    .order_by(desc(Message.created_at)).first()
                
                if latest_message:
                    conversation_data['latest_message'] = latest_message.to_dict()
                
                conversations.append(conversation_data)
            
            return {
                'success': True,
                'conversations': conversations,
                'pagination': {
                    'page': clients.page,
                    'per_page': clients.per_page,
                    'total': clients.total,
                    'pages': clients.pages,
                    'has_next': clients.has_next,
                    'has_prev': clients.has_prev
                }
            }
            
        except Exception as e:
            self.logger.error(f"Get conversations error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch conversations'}
    
    def get_conversation_messages(self, user_id: int, client_id: int, 
                                page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """
        Get messages for a specific conversation
        """
        try:
            # Verify client belongs to user
            client = Client.query.filter_by(id=client_id, user_id=user_id).first()
            if not client:
                return {'success': False, 'error': 'Conversation not found'}
            
            # Get messages with pagination
            messages_query = Message.query.filter_by(client_id=client_id)\
                .order_by(desc(Message.created_at))
            
            messages = messages_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Mark messages as read
            unread_messages = Message.query.filter_by(
                client_id=client_id,
                direction='inbound',
                is_read=False
            ).all()
            
            for message in unread_messages:
                message.is_read = True
            
            client.unread_count = 0
            db.session.commit()
            
            return {
                'success': True,
                'messages': [msg.to_dict() for msg in messages.items],
                'client': client.to_dict(include_stats=True),
                'pagination': {
                    'page': messages.page,
                    'per_page': messages.per_page,
                    'total': messages.total,
                    'pages': messages.pages,
                    'has_next': messages.has_next,
                    'has_prev': messages.has_prev
                }
            }
            
        except Exception as e:
            self.logger.error(f"Get conversation messages error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch messages'}
    
    def _get_or_create_client(self, user_id: int, phone_number: str) -> Client:
        """Get existing client or create new one"""
        client = Client.query.filter_by(
            user_id=user_id, 
            phone_number=phone_number
        ).first()
        
        if not client:
            client = Client(
                user_id=user_id,
                phone_number=phone_number,
                name=f"Client {phone_number[-4:]}"  # Default name
            )
            db.session.add(client)
            db.session.flush()
        
        return client
    
    def _generate_ai_response(self, user: User, client: Client, message_body: str) -> Optional[Dict[str, Any]]:
        """Generate AI response for incoming message"""
        try:
            # Get conversation context (last 5 messages)
            context_messages = Message.query.filter_by(client_id=client.id)\
                .order_by(desc(Message.created_at))\
                .limit(5)\
                .all()
            
            context = []
            for msg in reversed(context_messages):
                role = 'user' if msg.direction == 'inbound' else 'assistant'
                context.append({
                    'role': role,
                    'content': msg.body
                })
            
            # Add current message
            context.append({
                'role': 'user',
                'content': message_body
            })
            
            # Get AI response
            ai_response = get_ai_response(
                messages=context,
                personality=client.ai_personality,
                custom_prompt=client.custom_ai_prompt
            )
            
            return ai_response
            
        except Exception as e:
            self.logger.error(f"AI response generation error: {str(e)}")
            return None