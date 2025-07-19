import os
import json
import time
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AIService:
    """AI service for generating SMS responses using local LLM"""
    
    def __init__(self):
        self.llm_server_url = os.getenv('LLM_SERVER_URL', 'http://10.0.0.4:8080/v1/chat/completions')
        self.model_name = os.getenv('LLM_MODEL_NAME', 'dolphin-mistral')
        self.max_response_length = 160  # SMS character limit
        self.default_temperature = 0.7
        self.request_timeout = 30  # 30 seconds timeout
        
    def generate_response(self, user, incoming_message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Generate AI response for incoming message
        
        Args:
            user: User object with AI settings
            incoming_message: The incoming message text
            conversation_history: Previous messages in conversation
            
        Returns:
            Dict with response, confidence, and metadata
        """
        start_time = time.time()
        
        try:
            # Build conversation context
            context = self._build_conversation_context(user, incoming_message, conversation_history)
            
            # Prepare AI prompt
            prompt = self._build_ai_prompt(user, context)
            
            # Call LLM server
            response_data = self._call_llm_server(prompt, user)
            
            # Process and validate response
            ai_response = self._process_ai_response(response_data, user)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'response': ai_response['text'],
                'confidence': ai_response['confidence'],
                'processing_time': processing_time,
                'tokens_used': response_data.get('usage', {}).get('total_tokens', 0),
                'model_used': self.model_name
            }
            
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            processing_time = time.time() - start_time
            
            # Return fallback response
            return {
                'success': False,
                'response': self._get_fallback_response(user),
                'confidence': 0.1,
                'processing_time': processing_time,
                'error': str(e)
            }
    
    def _build_conversation_context(self, user, incoming_message: str, conversation_history: List[Dict] = None) -> Dict:
        """Build context for AI conversation"""
        context = {
            'user_info': {
                'name': user.full_name,
                'business_type': 'service professional',
                'phone_number': user.signalwire_phone_number
            },
            'current_message': incoming_message,
            'conversation_history': conversation_history or [],
            'timestamp': datetime.utcnow().isoformat(),
            'is_business_hours': self._is_business_hours(user)
        }
        
        return context
    
    def _build_ai_prompt(self, user, context: Dict) -> str:
        """Build AI prompt for response generation"""
        
        # Get user's AI personality settings
        try:
            ai_personality = json.loads(user.ai_personality) if user.ai_personality else {}
        except (json.JSONDecodeError, TypeError):
            ai_personality = {}
        
        # Base personality traits
        personality_traits = ai_personality.get('traits', {
            'tone': 'professional and friendly',
            'style': 'helpful and concise',
            'formality': 'casual but respectful'
        })
        
        # Build conversation history string
        history_str = ""
        if context['conversation_history']:
            history_str = "\n\nRecent conversation history:\n"
            for msg in context['conversation_history'][-5:]:  # Last 5 messages
                direction = "Client" if msg.get('direction') == 'inbound' else "You"
                body = msg.get('body', '')
                history_str += f"{direction}: {body}\n"
        
        # Current time context
        time_context = ""
        if not context['is_business_hours']:
            time_context = "\nNote: This message was received outside business hours. Consider mentioning when you'll be available."
        
        prompt = f"""You are an AI assistant responding to SMS messages for {context['user_info']['name']}, a service professional.

Your personality and communication style:
- Tone: {personality_traits['tone']}
- Style: {personality_traits['style']}
- Formality: {personality_traits['formality']}

Important guidelines:
- Keep responses under 160 characters when possible
- Be helpful and professional
- Respond as if you are {context['user_info']['name']}
- Don't mention that you're an AI
- If you can't help with something, suggest they call or schedule a meeting
- For scheduling requests, be helpful but don't commit to specific times without confirmation

{history_str}

{time_context}

Current message from client: "{context['current_message']}"

Generate a helpful, professional SMS response:"""

        return prompt
    
    def _call_llm_server(self, prompt: str, user) -> Dict:
        """Call the local LLM server"""
        
        # Get user-specific AI settings
        try:
            ai_personality = json.loads(user.ai_personality) if user.ai_personality else {}
        except (json.JSONDecodeError, TypeError):
            ai_personality = {}
            
        temperature = ai_personality.get('temperature', self.default_temperature)
        max_tokens = ai_personality.get('max_tokens', 200)
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful SMS assistant for a service professional. Keep responses concise and professional."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                self.llm_server_url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"LLM server error: {response.status_code} - {response.text}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise Exception("LLM server timeout")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to LLM server")
        except requests.exceptions.RequestException as e:
            raise Exception(f"LLM server request failed: {e}")
    
    def _process_ai_response(self, response_data: Dict, user) -> Dict:
        """Process and validate AI response"""
        
        try:
            # Extract response text
            choices = response_data.get('choices', [])
            if not choices:
                raise Exception("No choices in LLM response")
                
            ai_text = choices[0].get('message', {}).get('content', '').strip()
            
            if not ai_text:
                raise Exception("Empty response from LLM")
            
            # Remove any quotes if the AI wrapped the response
            if ai_text.startswith('"') and ai_text.endswith('"'):
                ai_text = ai_text[1:-1]
            
            # Truncate if too long (leave room for continuation indicator)
            if len(ai_text) > self.max_response_length - 3:
                ai_text = ai_text[:self.max_response_length - 3] + "..."
            
            # Calculate confidence based on response quality
            confidence = self._calculate_response_confidence(ai_text, response_data)
            
            return {
                'text': ai_text,
                'confidence': confidence
            }
            
        except (KeyError, IndexError, TypeError) as e:
            raise Exception(f"Invalid LLM response format: {e}")
    
    def _calculate_response_confidence(self, response_text: str, response_data: Dict) -> float:
        """Calculate confidence score for AI response"""
        confidence = 0.8  # Base confidence
        
        # Adjust based on response length
        if len(response_text) < 10:
            confidence -= 0.2
        elif len(response_text) > 150:
            confidence -= 0.1
        
        # Check for common AI artifacts
        ai_indicators = ['as an ai', 'i am an ai', 'i cannot', 'i am not able']
        if any(indicator in response_text.lower() for indicator in ai_indicators):
            confidence -= 0.3
        
        # Check if response seems relevant (contains question words, actionable content)
        relevant_words = ['when', 'where', 'how', 'yes', 'no', 'sure', 'thanks', 'schedule', 'appointment']
        if any(word in response_text.lower() for word in relevant_words):
            confidence += 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _get_fallback_response(self, user) -> str:
        """Get fallback response when AI fails"""
        fallback_responses = [
            "Thanks for your message! I'll get back to you soon.",
            "Hi! I received your message and will respond shortly.",
            "Thank you for reaching out. I'll be in touch soon!",
            "Got your message! I'll respond as soon as I can."
        ]
        
        import random
        return random.choice(fallback_responses)
    
    def _is_business_hours(self, user) -> bool:
        """Check if current time is within business hours"""
        if not user.business_hours:
            return True
        
        try:
            business_hours = user.business_hours
            if not business_hours.get('enabled', True):
                return True
            
            # This is a simplified version - you might want to use the same
            # logic from the webhooks file for consistency
            from datetime import datetime
            now = datetime.utcnow()
            current_hour = now.hour
            
            start_hour = int(business_hours.get('start_time', '09:00').split(':')[0])
            end_hour = int(business_hours.get('end_time', '17:00').split(':')[0])
            
            return start_hour <= current_hour <= end_hour
            
        except (ValueError, TypeError, AttributeError):
            return True  # Default to available if parsing fails
    
    def analyze_message_intent(self, message_text: str) -> Dict:
        """Analyze message intent for better response routing"""
        intents = {
            'scheduling': ['appointment', 'schedule', 'book', 'available', 'when'],
            'question': ['?', 'how', 'what', 'when', 'where', 'why'],
            'emergency': ['urgent', 'emergency', 'asap', 'now', 'help'],
            'greeting': ['hello', 'hi', 'hey', 'good morning', 'good afternoon'],
            'cancellation': ['cancel', 'reschedule', 'change', 'move'],
            'pricing': ['cost', 'price', 'how much', 'rate', 'fee']
        }
        
        message_lower = message_text.lower()
        detected_intents = []
        
        for intent, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intents.append(intent)
        
        return {
            'primary_intent': detected_intents[0] if detected_intents else 'general',
            'all_intents': detected_intents,
            'confidence': 0.8 if detected_intents else 0.3
        }