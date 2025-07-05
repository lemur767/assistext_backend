"""
Custom AI Service for Self-Hosted LLM Server
app/services/ai_service.py - Replaces OpenAI with your own LLM server
"""
import os
import requests
import json
import logging
from typing import Dict, Any, Optional, List
from flask import current_app
from app.models.profile import Profile
from app.models.message import Message
from app.models.client import Client
import time

class AIService:
    """
    Custom AI Service for Self-Hosted LLM Server
    Supports your dolphin-mistral model and custom configuration
    """
    
    def __init__(self):
        # LLM Server Configuration
        self.llm_url = os.getenv('LLM_SERVER_URL', 'http://10.0.0.4:8080')
        self.model = os.getenv('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
        self.timeout = int(os.getenv('LLM_TIMEOUT', '30'))
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '150'))
        self.temperature = float(os.getenv('LLM_TEMPERATURE', '0.7'))
        self.retry_attempts = int(os.getenv('LLM_RETRY_ATTEMPTS', '2'))
        
        # Safety and rate limiting
        self.max_daily_responses = int(os.getenv('MAX_DAILY_AI_RESPONSES', '100'))
        self.max_messages_per_5min = int(os.getenv('MAX_MESSAGES_PER_5MIN', '3'))
        
        # Fallback responses for when LLM is unavailable
        self.fallback_responses = [
            "Thanks for your message! I'll get back to you soon. 😊",
            "Hi there! I received your message and will respond shortly.",
            "Thank you for reaching out! I'll reply as soon as possible.",
            "Got your message! I'll be in touch soon. 💕",
            "Thanks for texting! I'll respond when I'm available."
        ]
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def is_configured(self) -> bool:
        """Check if AI service is properly configured"""
        return bool(self.llm_url and self.model)
    
    def _check_rate_limits(self, sender_number: str) -> bool:
        """
        Check if sender has exceeded rate limits
        Returns True if within limits, False if exceeded
        """
        try:
            # Check 5-minute rate limit
            five_min_ago = time.time() - 300  # 5 minutes
            
            # In a real implementation, you'd check against Redis or database
            # For now, we'll assume rate limits are OK
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit check error: {str(e)}")
            return True  # Allow if check fails
    
    def _get_conversation_history(self, profile_id: int, sender_number: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation history for context"""
        try:
            if not profile_id:
                return []
            
            # Get recent messages between this sender and profile
            recent_messages = Message.query.filter(
                Message.profile_id == profile_id,
                Message.sender_number == sender_number
            ).order_by(Message.timestamp.desc()).limit(limit * 2).all()
            
            # Format conversation history
            history = []
            for msg in reversed(recent_messages):
                if msg.direction == 'inbound':
                    history.append({
                        'role': 'user',
                        'content': msg.message_body,
                        'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                    })
                elif msg.direction == 'outbound':
                    history.append({
                        'role': 'assistant', 
                        'content': msg.message_body,
                        'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                    })
            
            return history[-limit:] if len(history) > limit else history
            
        except Exception as e:
            self.logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    def _build_system_prompt(self, profile: Optional[Profile], client_info: Optional[Dict] = None) -> str:
        """Build system prompt based on profile configuration"""
        
        if profile and profile.ai_persona:
            # Use custom persona from profile
            system_prompt = profile.ai_persona
        else:
            # Default professional persona
            system_prompt = """You are a professional and friendly assistant responding to text messages. 
Your responses should be:
- Helpful and courteous
- Brief but informative (1-2 sentences max)
- Professional yet warm in tone
- Appropriate for SMS communication

Keep responses under 160 characters when possible. Use emojis sparingly and only when appropriate."""
        
        # Add profile-specific context
        if profile:
            if profile.business_type:
                system_prompt += f"\n\nYou work in the {profile.business_type} industry."
            
            if profile.response_style:
                system_prompt += f"\n\nResponse style preferences: {profile.response_style}"
            
            if hasattr(profile, 'writing_style') and profile.writing_style:
                system_prompt += f"\n\nWriting style: {profile.writing_style}"
        
        # Add client context if available
        if client_info:
            if client_info.get('is_regular_client'):
                system_prompt += "\n\nThis is a regular client, so you can be more familiar in your tone."
            
            if client_info.get('last_interaction'):
                system_prompt += f"\n\nLast interaction was: {client_info['last_interaction']}"
        
        return system_prompt
    
    def _call_llm_server(self, messages: List[Dict], retries: int = 0) -> Optional[str]:
        """Make API call to self-hosted LLM server"""
        try:
            # Format request for your LLM server
            # Adjust this based on your LLM server's API format
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": False,
                "stop": ["\n\n", "User:", "Client:", "Me:"]
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Add API key if your server requires it
            api_key = os.getenv('LLM_API_KEY')
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            self.logger.info(f"Calling LLM server: {self.llm_url}")
            
            # Make request to LLM server
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",  # OpenAI-compatible endpoint
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract response based on your LLM server's response format
                if 'choices' in result and len(result['choices']) > 0:
                    ai_response = result['choices'][0]['message']['content'].strip()
                elif 'response' in result:
                    ai_response = result['response'].strip()
                else:
                    self.logger.error(f"Unexpected LLM response format: {result}")
                    return None
                
                # Clean up the response
                ai_response = self._clean_response(ai_response)
                
                self.logger.info(f"LLM response: {ai_response[:100]}...")
                return ai_response
                
            else:
                self.logger.error(f"LLM server error {response.status_code}: {response.text}")
                
                # Retry if configured and not final attempt
                if retries < self.retry_attempts:
                    self.logger.info(f"Retrying LLM request (attempt {retries + 1}/{self.retry_attempts})")
                    time.sleep(1)  # Brief delay before retry
                    return self._call_llm_server(messages, retries + 1)
                
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("LLM server timeout")
            if retries < self.retry_attempts:
                return self._call_llm_server(messages, retries + 1)
            return None
            
        except requests.exceptions.ConnectionError:
            self.logger.error("Cannot connect to LLM server")
            return None
            
        except Exception as e:
            self.logger.error(f"LLM server request error: {str(e)}")
            return None
    
    def _clean_response(self, response: str) -> str:
        """Clean and validate AI response"""
        if not response:
            return ""
        
        # Remove common artifacts
        response = response.strip()
        
        # Remove quotes if the entire response is quoted
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        # Remove any trailing punctuation repetition
        while response.endswith('...') or response.endswith('!!!'):
            response = response[:-1].rstrip('.')
        
        # Ensure reasonable length (SMS friendly)
        if len(response) > 320:  # 2 SMS limit
            response = response[:300] + "..."
        
        return response
    
    def _get_fallback_response(self, message: str) -> str:
        """Get fallback response when LLM is unavailable"""
        # Simple keyword-based responses for common scenarios
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "Hi there! Thanks for your message. I'll get back to you soon! 😊"
        elif any(word in message_lower for word in ['help', 'info', 'information']):
            return "I'd be happy to help! Let me get back to you with more information shortly."
        elif any(word in message_lower for word in ['thanks', 'thank you']):
            return "You're welcome! Feel free to reach out anytime. 😊"
        elif 'stop' in message_lower:
            return "You have been unsubscribed. Reply START to opt back in."
        elif 'start' in message_lower:
            return "Welcome back! You're subscribed to receive messages."
        else:
            # Use random fallback response
            import random
            return random.choice(self.fallback_responses)
    
    def generate_response(self, profile: Optional[Profile], message: str, 
                         sender_number: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        Generate AI response to incoming message
        
        Args:
            profile: User profile configuration
            message: Incoming message text
            sender_number: Sender's phone number
            context: Additional context (message_sid, etc.)
            
        Returns:
            Generated response string or None if failed
        """
        try:
            # Check rate limits
            if not self._check_rate_limits(sender_number):
                self.logger.warning(f"Rate limit exceeded for {sender_number}")
                return "I'm receiving a lot of messages right now. Please give me a moment to respond!"
            
            # Get client information for context
            client = Client.query.filter_by(phone_number=sender_number).first()
            client_info = {}
            if client:
                client_info = {
                    'is_regular_client': client.is_regular if hasattr(client, 'is_regular') else False,
                    'last_interaction': client.last_contact.isoformat() if client.last_contact else None
                }
            
            # Build system prompt
            system_prompt = self._build_system_prompt(profile, client_info)
            
            # Get conversation history
            history = self._get_conversation_history(
                profile.id if profile else None, 
                sender_number, 
                limit=3
            )
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history
            messages.extend(history)
            
            # Add current message
            messages.append({
                "role": "user", 
                "content": message
            })
            
            # Try to get response from LLM server
            if self.is_configured():
                ai_response = self._call_llm_server(messages)
                
                if ai_response:
                    return ai_response
                else:
                    self.logger.warning("LLM server unavailable, using fallback")
            else:
                self.logger.warning("LLM service not configured, using fallback")
            
            # Return fallback response if LLM fails
            return self._get_fallback_response(message)
            
        except Exception as e:
            self.logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
            return self._get_fallback_response(message)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to LLM server"""
        try:
            test_payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "Hello, this is a test message."}
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            headers = {"Content-Type": "application/json"}
            api_key = os.getenv('LLM_API_KEY')
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json=test_payload,
                headers=headers,
                timeout=10
            )
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'server_url': self.llm_url,
                'model': self.model,
                'error': response.text if response.status_code != 200 else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'server_url': self.llm_url,
                'model': self.model
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get AI service status and configuration"""
        return {
            'configured': self.is_configured(),
            'llm_url': self.llm_url,
            'model': self.model,
            'timeout': self.timeout,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'retry_attempts': self.retry_attempts,
            'max_daily_responses': self.max_daily_responses,
            'fallback_responses_count': len(self.fallback_responses)
        }