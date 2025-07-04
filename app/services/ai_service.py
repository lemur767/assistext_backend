from app.models.user import User
from app.models.client import Client
from app.models.message import Message
from app.utils.signalwire_helpers import send_sms
from typing import Dict, Any, Optional
from app.extensions import db
import time
from datetime import datetime

class AIService:
    """Service for handling AI-powered message responses"""
    
    @staticmethod
    def process_incoming_message(from_number: str, to_number: str, content: str) -> Dict[str, Any]:
        """
        Process an incoming SMS and generate AI response based on user's settings
        
        Args:
            from_number: Client's phone number
            to_number: User's SignalWire phone number  
            content: Message content
            
        Returns:
            Dict with processing results
        """
        try:
            # Find the user by their SignalWire phone number
            user = User.query.filter_by(signalwire_phone_number=to_number).first()
            
            if not user:
                return {
                    'success': False,
                    'error': 'No user found for this phone number',
                    'user_found': False
                }
            
            # Check if user has AI enabled
            if not user.ai_enabled:
                return {
                    'success': False,
                    'error': 'AI responses disabled for this user',
                    'user_found': True,
                    'ai_enabled': False
                }
            
            # Find or create client
            client = Client.query.filter_by(
                user_id=user.id,
                phone_number=from_number
            ).first()
            
            if not client:
                client = Client(
                    user_id=user.id,
                    phone_number=from_number,
                    first_contact=datetime.utcnow(),
                    last_interaction=datetime.utcnow()
                )
                db.session.add(client)
                db.session.flush()  # Get the client ID
            else:
                client.update_interaction()
            
            # Check if client is blocked
            if client.is_blocked:
                return {
                    'success': False,
                    'error': 'Client is blocked',
                    'user_found': True,
                    'client_blocked': True
                }
            
            # Save incoming message
            incoming_message = Message(
                user_id=user.id,
                client_id=client.id,
                content=content,
                direction='incoming',
                from_number=from_number,
                to_number=to_number,
                status='delivered'
            )
            db.session.add(incoming_message)
            
            # Check daily message limit
            user.reset_monthly_count_if_needed()
            if user.monthly_message_count >= (user.daily_message_limit * 30):
                return {
                    'success': False,
                    'error': 'Daily message limit exceeded',
                    'user_found': True,
                    'limit_exceeded': True
                }
            
            # Generate AI response
            ai_response = AIService._generate_ai_response(user, client, content)
            
            if not ai_response['success']:
                return ai_response
            
            # Send the response via SignalWire
            send_result = send_sms(
                to=from_number,
                message=ai_response['response'],
                from_number=to_number
            )
            
            if send_result['success']:
                # Save outgoing message
                outgoing_message = Message(
                    user_id=user.id,
                    client_id=client.id,
                    content=ai_response['response'],
                    direction='outgoing',
                    from_number=to_number,
                    to_number=from_number,
                    was_ai_generated=True,
                    ai_model_used=user.ai_model,
                    ai_processing_time=ai_response.get('processing_time', 0),
                    ai_confidence=ai_response.get('confidence', 0.8),
                    status='delivered',
                    signalwire_sid=send_result.get('sid')
                )
                db.session.add(outgoing_message)
                
                # Update usage counters
                user.update_message_count(sent=1, received=1)
                
                db.session.commit()
                
                return {
                    'success': True,
                    'message': 'AI response sent successfully',
                    'response_content': ai_response['response'],
                    'user_id': user.id,
                    'client_id': client.id
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to send SMS: {send_result['error']}",
                    'user_found': True,
                    'sms_failed': True
                }
                
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f"Processing error: {str(e)}",
                'exception': True
            }
    
    @staticmethod
    def _generate_ai_response(user: User, client: Client, message_content: str) -> Dict[str, Any]:
        """Generate AI response using user's settings"""
        try:
            start_time = time.time()
            
            # Get AI settings for this user
            ai_settings = user.get_ai_settings()
            
            # Use client-specific personality if available
            personality = client.get_ai_personality()
            
            # Get recent conversation context
            recent_messages = Message.query.filter_by(
                user_id=user.id,
                client_id=client.id
            ).order_by(Message.created_at.desc()).limit(10).all()
            
            # Build conversation context
            context_messages = []
            for msg in reversed(recent_messages):
                role = "user" if msg.direction == "incoming" else "assistant"
                context_messages.append({
                    "role": role,
                    "content": msg.content
                })
            
            # Add the current message
            context_messages.append({
                "role": "user",
                "content": message_content
            })
            
            # Create system prompt
            system_prompt = f"""
            {personality}
            
            Additional instructions: {ai_settings['instructions']}
            
            You are responding to messages from a client named {client.get_display_name()}.
            Client status: {client.relationship_status}
            
            Keep responses concise and appropriate for SMS. Respond naturally and helpfully.
            """
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=ai_settings['model'],
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    *context_messages
                ],
                temperature=ai_settings['temperature'],
                max_tokens=ai_settings['max_tokens']
            )
            
            ai_response = response.choices[0].message.content.strip()
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'response': ai_response,
                'processing_time': processing_time,
                'confidence': 0.8,  # Could be calculated based on response quality
                'model_used': ai_settings['model']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"AI generation failed: {str(e)}"
            }
