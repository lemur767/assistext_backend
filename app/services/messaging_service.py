from typing import Dict, Any, Optional, List
from app.extensions import db
from app.models.messaging import Message, Client
from app.models.user import User
from app.utils.external_clients import SignalWireClient, LLMClient
from app.services.billing_service import BillingService


class MessagingService:
    """Unified messaging operations service"""
    
    # =============================================================================
    # SMS OPERATIONS
    # =============================================================================
    
    @staticmethod
    def send_sms(user_id: int, to_number: str, content: str, ai_generated: bool = False) -> Message:
        """Send SMS message"""
        try:
            # Check usage limits
            if not BillingService.check_usage_limits(user_id, 'sms_messages'):
                raise Exception("SMS usage limit exceeded")
            
            user = User.query.get_or_404(user_id)
            if not user.signalwire_phone_number:
                raise Exception("No SignalWire phone number configured")
            
            # Send via SignalWire
            signalwire = SignalWireClient()
            result = signalwire.send_message(
                from_number=user.signalwire_phone_number,
                to_number=to_number,
                content=content
            )
            
            # Get or create client
            client = MessagingService._get_or_create_client(user_id, to_number)
            
            # Save message record
            message = Message(
                user_id=user_id,
                client_id=client.id,
                content=content,
                is_incoming=False,
                sender_number=user.signalwire_phone_number,
                recipient_number=to_number,
                ai_generated=ai_generated,
                signalwire_sid=result.sid,
                status='sent'
            )
            
            db.session.add(message)
            
            # Track usage
            BillingService.track_usage(user_id, 'sms_messages', 1)
            
            db.session.commit()
            
            return message
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to send SMS: {str(e)}")
    
    @staticmethod
    def process_incoming_message(from_number: str, to_number: str, content: str) -> Optional[str]:
        """Process incoming SMS and generate AI response"""
        try:
            # Find user by phone number
            user = User.query.filter_by(signalwire_phone_number=to_number).first()
            if not user:
                return None
            
            # Get or create client
            client = MessagingService._get_or_create_client(user.id, from_number)
            
            # Save incoming message
            incoming_message = Message(
                user_id=user.id,
                client_id=client.id,
                content=content,
                is_incoming=True,
                sender_number=from_number,
                recipient_number=to_number,
                ai_generated=False,
                status='received'
            )
            
            db.session.add(incoming_message)
            db.session.commit()
            
            # Generate AI response if enabled
            if user.ai_enabled and BillingService.check_usage_limits(user.id, 'ai_responses'):
                response_content = MessagingService._generate_ai_response(user, client, content)
                
                # Send AI response
                if response_content:
                    MessagingService.send_sms(user.id, from_number, response_content, ai_generated=True)
                    BillingService.track_usage(user.id, 'ai_responses', 1)
                    return response_content
            
            return None
            
        except Exception as e:
            raise Exception(f"Failed to process incoming message: {str(e)}")
    
    # =============================================================================
    # AI RESPONSE GENERATION
    # =============================================================================
    
    @staticmethod
    def _generate_ai_response(user: User, client: Client, message_content: str) -> Optional[str]:
        """Generate AI response using LLM"""
        try:
            # Get conversation context
            recent_messages = Message.query.filter_by(
                user_id=user.id,
                client_id=client.id
            ).order_by(Message.timestamp.desc()).limit(5).all()
            
            # Build context
            context = []
            for msg in reversed(recent_messages):
                role = "user" if msg.is_incoming else "assistant"
                context.append(f"{role}: {msg.content}")
            
            # Add current message
            context.append(f"user: {message_content}")
            
            # Generate response
            llm_client = LLMClient()
            response = llm_client.generate_response(
                prompt="\n".join(context),
                personality=user.ai_personality,
                custom_instructions=user.custom_ai_instructions
            )
            
            return response
            
        except Exception as e:
            print(f"AI response generation failed: {str(e)}")
            return None
    
    # =============================================================================
    # CLIENT MANAGEMENT
    # =============================================================================
    
    @staticmethod
    def _get_or_create_client(user_id: int, phone_number: str) -> Client:
        """Get existing client or create new one"""
        client = Client.query.filter_by(
            user_id=user_id,
            phone_number=phone_number
        ).first()
        
        if not client:
            client = Client(
                user_id=user_id,
                phone_number=phone_number,
                relationship_status='new'
            )
            db.session.add(client)
            db.session.flush()  # Get ID without committing
        
        return client
    
    @staticmethod
    def get_conversation_history(user_id: int, client_id: int, limit: int = 50) -> List[Message]:
        """Get conversation history with client"""
        return Message.query.filter_by(
            user_id=user_id,
            client_id=client_id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    @staticmethod
    def get_user_clients(user_id: int) -> List[Client]:
        """Get all clients for user"""
        return Client.query.filter_by(user_id=user_id).order_by(Client.created_at.desc()).all()
