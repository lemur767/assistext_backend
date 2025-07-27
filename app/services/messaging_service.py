
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import logging
import re

from flask import current_app
from flask_sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.messaging import Message, Client, MessageTemplate, ActivityLog
from app.models.user import User
from app.utils.llm_client import OllamaLLMClient
from app.services.signalwire_service import SignalWireService
from app.services.billing_service import BillingService


class MessagingService:
    """Unified messaging operations service"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.signalwire_client = SignalWireService()
        self.llm_client = OllamaLLMClient()
        self.billing_service = BillingService()
    
    # =============================================================================
    # SMS OPERATIONS
    # =============================================================================
    
    def send_sms(self, user_id: int, to_number: str, content: str, 
                ai_generated: bool = False, template_id: int = None) -> Message:
        """Send SMS message with usage tracking"""
        try:
            # Check usage limits first
            can_send, limit_info = self.billing_service.check_usage_limits(user_id, 'sms_messages')
            if not can_send:
                raise Exception(f"SMS usage limit exceeded. {limit_info.get('remaining', 0)} messages remaining.")
            
            user = User.query.get_or_404(user_id)
            if not user.signalwire_phone_number:
                raise Exception("No SignalWire phone number configured")
            
            # Validate and format content
            content = self._validate_message_content(content)
            
            # Get or create client
            client = self._get_or_create_client(user_id, to_number)
            
            # Check for flagged content if enabled
            if user.enable_flagged_word_detection:
                is_flagged, flag_reasons = self._check_flagged_content(content, user.flagged_words_list)
                if is_flagged and user.require_manual_review:
                    raise Exception(f"Message flagged for review: {', '.join(flag_reasons)}")
            else:
                is_flagged, flag_reasons = False, []
            
            # Send via SignalWire
            result = self.signalwire_client.send_message(
                from_number=user.signalwire_phone_number,
                to_number=to_number,
                content=content
            )
            
            # Save message record
            message = Message(
                user_id=user_id,
                client_id=client.id,
                content=content,
                is_incoming=False,
                sender_number=user.signalwire_phone_number,
                recipient_number=to_number,
                ai_generated=ai_generated,
                is_flagged=is_flagged,
                flag_reasons=flag_reasons if flag_reasons else None,
                signalwire_sid=result.sid,
                status='sent',
                sent_at=datetime.utcnow()
            )
            
            db.session.add(message)
            
            # Update client interaction tracking
            self._update_client_interaction(client, outgoing=True)
            
            # Track usage for billing
            self.billing_service.track_usage(user_id, 'sms_messages', 1, {
                'message_id': None,  # Will be set after commit
                'ai_generated': ai_generated,
                'client_id': client.id
            })
            
            # Update template usage if applicable
            if template_id:
                self._update_template_usage(template_id)
            
            db.session.commit()
            
            # Update usage metadata with message ID
            if message.id:
                self.billing_service.track_usage(user_id, 'sms_messages', 0, {
                    'message_id': message.id,
                    'update': True
                })
            
            self.logger.info(f"Sent SMS to {to_number} for user {user_id}")
            return message
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to send SMS: {str(e)}")
            raise Exception(f"Failed to send SMS: {str(e)}")
    
    def process_incoming_message(self, from_number: str, to_number: str, 
                               content: str, signalwire_sid: str = None) -> Optional[Message]:
        """Process incoming SMS and generate AI response if enabled"""
        try:
            # Find user by phone number
            user = User.query.filter_by(signalwire_phone_number=to_number).first()
            if not user:
                self.logger.warning(f"No user found for phone number {to_number}")
                return None
            
            # Validate and clean content
            content = self._validate_message_content(content)
            
            # Get or create client
            client = self._get_or_create_client(user.id, from_number)
            
            # Check for flagged content
            is_flagged, flag_reasons = False, []
            if user.enable_flagged_word_detection:
                is_flagged, flag_reasons = self._check_flagged_content(content, user.flagged_words_list)
            
            # Save incoming message
            incoming_message = Message(
                user_id=user.id,
                client_id=client.id,
                content=content,
                is_incoming=True,
                sender_number=from_number,
                recipient_number=to_number,
                ai_generated=False,
                is_flagged=is_flagged,
                flag_reasons=flag_reasons if flag_reasons else None,
                signalwire_sid=signalwire_sid,
                status='received'
            )
            
            db.session.add(incoming_message)
            
            # Update client interaction tracking
            self._update_client_interaction(client, incoming=True)
            
            db.session.commit()
            
            # Generate AI response if conditions are met
            ai_response_message = None
            if self._should_generate_ai_response(user, client, content, is_flagged):
                ai_response_message = self._generate_and_send_ai_response(
                    user, client, content, incoming_message.id
                )
            
            self.logger.info(f"Processed incoming message from {from_number} for user {user.id}")
            return ai_response_message or incoming_message
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to process incoming message: {str(e)}")
            raise Exception(f"Failed to process incoming message: {str(e)}")
    
    # =============================================================================
    # AI RESPONSE GENERATION
    # =============================================================================
    
    def _should_generate_ai_response(self, user: User, client: Client, 
                                   content: str, is_flagged: bool) -> bool:
        """Determine if AI response should be generated"""
        # Check if AI is enabled
        if not user.ai_enabled:
            return False
        
        # Don't respond to flagged messages if auto-block is enabled
        if is_flagged and user.auto_block_suspicious:
            return False
        
        # Don't respond if client is blocked
        if client.is_blocked:
            return False
        
        # Check business hours
        if not user.is_in_business_hours and user.business_hours_enabled:
            # Send after-hours message if configured
            if user.after_hours_message:
                self._send_after_hours_message(user, client)
            return False
        
        # Check if out of office
        if user.is_out_of_office:
            if user.out_of_office_message:
                self._send_out_of_office_message(user, client)
            return False
        
        # Check AI usage limits
        can_use_ai, _ = self.billing_service.check_usage_limits(user.id, 'ai_responses')
        if not can_use_ai:
            return False
        
        return True
    
    def _generate_and_send_ai_response(self, user: User, client: Client, 
                                     message_content: str, incoming_message_id: int) -> Optional[Message]:
        """Generate and send AI response"""
        try:
            # Get conversation context
            conversation_history = self._get_conversation_context(user.id, client.id)
            
            # Generate AI response
            ai_response = self.llm_client.generate_response(
                prompt=message_content,
                personality=user.ai_personality,
                custom_instructions=user.custom_ai_instructions,
                conversation_history=conversation_history,
                client_context=self._build_client_context(client)
            )
            
            if not ai_response:
                self.logger.warning(f"No AI response generated for user {user.id}")
                return None
            
            # Apply user preferences to response
            ai_response = self._apply_response_preferences(ai_response, user)
            
            # Send AI response
            response_message = self.send_sms(
                user_id=user.id,
                to_number=client.phone_number,
                content=ai_response,
                ai_generated=True
            )
            
            # Track AI usage
            self.billing_service.track_usage(user.id, 'ai_responses', 1, {
                'incoming_message_id': incoming_message_id,
                'response_message_id': response_message.id,
                'client_id': client.id,
                'model_used': self.llm_client.model
            })
            
            self.logger.info(f"Generated AI response for user {user.id}, client {client.id}")
            return response_message
            
        except Exception as e:
            self.logger.error(f"Failed to generate AI response: {str(e)}")
            return None
    
    def _get_conversation_context(self, user_id: int, client_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation history for AI context"""
        messages = Message.query.filter_by(
            user_id=user_id,
            client_id=client_id
        ).order_by(desc(Message.timestamp)).limit(limit).all()
        
        context = []
        for msg in reversed(messages):
            role = "user" if msg.is_incoming else "assistant"
            context.append({
                "role": role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            })
        
        return context
    
    def _build_client_context(self, client: Client) -> Dict[str, Any]:
        """Build context about the client for AI"""
        return {
            "name": client.name,
            "nickname": client.nickname,
            "relationship_status": client.relationship_status,
            "total_interactions": client.total_interactions,
            "preferred_style": client.ai_response_style,
            "custom_greeting": client.custom_greeting,
            "notes": client.notes
        }
    
    def _apply_response_preferences(self, response: str, user: User) -> str:
        """Apply user preferences to AI response"""
        # Apply emoji preferences
        if not user.use_emojis:
            # Remove common emojis
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                "]+", flags=re.UNICODE
            )
            response = emoji_pattern.sub('', response).strip()
        
        # Apply casual language preferences
        if not user.casual_language:
            # Apply more formal language patterns
            response = response.replace(" u ", " you ")
            response = response.replace(" ur ", " your ")
            response = response.replace("cant", "cannot")
            response = response.replace("wont", "will not")
        
        return response.strip()
    
    def _send_after_hours_message(self, user: User, client: Client) -> None:
        """Send after-hours message"""
        try:
            self.send_sms(
                user_id=user.id,
                to_number=client.phone_number,
                content=user.after_hours_message,
                ai_generated=False
            )
        except Exception as e:
            self.logger.error(f"Failed to send after-hours message: {str(e)}")
    
    def _send_out_of_office_message(self, user: User, client: Client) -> None:
        """Send out of office message"""
        try:
            self.send_sms(
                user_id=user.id,
                to_number=client.phone_number,
                content=user.out_of_office_message,
                ai_generated=False
            )
        except Exception as e:
            self.logger.error(f"Failed to send out of office message: {str(e)}")
    
    # =============================================================================
    # CLIENT MANAGEMENT
    # =============================================================================
    
    def _get_or_create_client(self, user_id: int, phone_number: str, 
                            name: str = None) -> Client:
        """Get existing client or create new one"""
        client = Client.query.filter_by(
            user_id=user_id,
            phone_number=phone_number
        ).first()
        
        if not client:
            client = Client(
                user_id=user_id,
                phone_number=phone_number,
                name=name,
                relationship_status='new',
                auto_reply_enabled=True
            )
            db.session.add(client)
            db.session.flush()  # Get ID without committing
            
            self.logger.info(f"Created new client {client.id} for user {user_id}")
        
        return client
    
    def _update_client_interaction(self, client: Client, incoming: bool = False, 
                                 outgoing: bool = False) -> None:
        """Update client interaction statistics"""
        client.last_interaction = datetime.utcnow()
        client.total_interactions += 1
        
        if incoming:
            client.total_messages_received += 1
        if outgoing:
            client.total_messages_sent += 1
    
    def get_client_conversation(self, user_id: int, client_id: int, 
                              limit: int = 100, offset: int = 0) -> List[Message]:
        """Get conversation history with client"""
        return Message.query.filter_by(
            user_id=user_id,
            client_id=client_id
        ).order_by(desc(Message.timestamp)).offset(offset).limit(limit).all()
    
    def get_user_clients(self, user_id: int, include_blocked: bool = False, 
                        search: str = None) -> List[Client]:
        """Get all clients for user with optional filtering"""
        query = Client.query.filter_by(user_id=user_id)
        
        if not include_blocked:
            query = query.filter_by(is_blocked=False)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Client.name.ilike(search_pattern),
                    Client.phone_number.ilike(search_pattern),
                    Client.email.ilike(search_pattern)
                )
            )
        
        return query.order_by(desc(Client.last_interaction)).all()
    
    def update_client(self, client_id: int, **updates) -> Client:
        """Update client information"""
        try:
            client = Client.query.get_or_404(client_id)
            
            # Update allowed fields
            allowed_fields = [
                'name', 'nickname', 'email', 'notes', 'relationship_status',
                'priority_level', 'is_favorite', 'tags', 'custom_ai_personality',
                'custom_greeting', 'ai_response_style'
            ]
            
            for field in allowed_fields:
                if field in updates:
                    setattr(client, field, updates[field])
            
            client.updated_at = datetime.utcnow()
            db.session.commit()
            
            return client
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to update client: {str(e)}")
            raise Exception(f"Failed to update client: {str(e)}")
    
    def block_client(self, client_id: int, reason: str = None) -> bool:
        """Block client from sending messages"""
        try:
            client = Client.query.get_or_404(client_id)
            client.is_blocked = True
            client.block_reason = reason
            client.blocked_at = datetime.utcnow()
            
            db.session.commit()
            self.logger.info(f"Blocked client {client_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to block client: {str(e)}")
            return False
    
    # =============================================================================
    # MESSAGE TEMPLATES
    # =============================================================================
    
    def create_template(self, user_id: int, name: str, content: str, 
                       category: str = None, variables: Dict = None) -> MessageTemplate:
        """Create message template"""
        try:
            template = MessageTemplate(
                user_id=user_id,
                name=name,
                content=content,
                category=category,
                variables=variables or {}
            )
            
            db.session.add(template)
            db.session.commit()
            
            self.logger.info(f"Created template {template.id} for user {user_id}")
            return template
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create template: {str(e)}")
            raise Exception(f"Failed to create template: {str(e)}")
    
    def use_template(self, template_id: int, variables: Dict = None) -> str:
        """Use template with variable substitution"""
        template = MessageTemplate.query.get_or_404(template_id)
        
        content = template.content
        if variables and template.variables:
            for var_name, var_value in variables.items():
                if var_name in template.variables:
                    content = content.replace(f"{{{var_name}}}", str(var_value))
        
        # Update usage tracking
        self._update_template_usage(template_id)
        
        return content
    
    def _update_template_usage(self, template_id: int) -> None:
        """Update template usage statistics"""
        try:
            template = MessageTemplate.query.get(template_id)
            if template:
                template.usage_count += 1
                template.last_used_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to update template usage: {str(e)}")
    
    # =============================================================================
    # CONTENT MODERATION
    # =============================================================================
    
    def _check_flagged_content(self, content: str, flagged_words: List[str]) -> Tuple[bool, List[str]]:
        """Check content for flagged words"""
        if not flagged_words:
            return False, []
        
        content_lower = content.lower()
        found_words = []
        
        for word in flagged_words:
            if word.lower() in content_lower:
                found_words.append(word)
        
        return len(found_words) > 0, found_words
    
    def _validate_message_content(self, content: str) -> str:
        """Validate and clean message content"""
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")
        
        # Trim whitespace
        content = content.strip()
        
        # Check length (SMS limit)
        if len(content) > 1600:  # Allow for longer messages that will be split
            self.logger.warning(f"Message length {len(content)} exceeds recommended SMS length")
        
        return content
    
    # =============================================================================
    # BULK OPERATIONS
    # =============================================================================
    
    def send_bulk_sms(self, user_id: int, recipients: List[str], content: str, 
                     template_id: int = None) -> Dict[str, Any]:
        """Send SMS to multiple recipients"""
        results = {
            'success': [],
            'failed': [],
            'total': len(recipients)
        }
        
        for phone_number in recipients:
            try:
                message = self.send_sms(
                    user_id=user_id,
                    to_number=phone_number,
                    content=content,
                    template_id=template_id
                )
                results['success'].append({
                    'phone_number': phone_number,
                    'message_id': message.id
                })
            except Exception as e:
                results['failed'].append({
                    'phone_number': phone_number,
                    'error': str(e)
                })
        
        self.logger.info(f"Bulk SMS for user {user_id}: {len(results['success'])} success, {len(results['failed'])} failed")
        return results
    
    # =============================================================================
    # ANALYTICS
    # =============================================================================
    
    def get_messaging_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get messaging analytics for user"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Message counts
        total_messages = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= start_date
        ).count()
        
        incoming_messages = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= start_date,
            Message.is_incoming == True
        ).count()
        
        outgoing_messages = total_messages - incoming_messages
        
        ai_generated = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= start_date,
            Message.ai_generated == True
        ).count()
        
        # Client metrics
        active_clients = Client.query.filter(
            Client.user_id == user_id,
            Client.last_interaction >= start_date
        ).count()
        
        new_clients = Client.query.filter(
            Client.user_id == user_id,
            Client.first_contact >= start_date
        ).count()
        
        return {
            'period_days': days,
            'total_messages': total_messages,
            'incoming_messages': incoming_messages,
            'outgoing_messages': outgoing_messages,
            'ai_generated_messages': ai_generated,
            'ai_response_rate': (ai_generated / incoming_messages * 100) if incoming_messages > 0 else 0,
            'active_clients': active_clients,
            'new_clients': new_clients,
            'messages_per_day': total_messages / days if days > 0 else 0
        }