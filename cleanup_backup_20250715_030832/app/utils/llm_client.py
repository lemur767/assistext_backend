"""
LLM Client for AI Response Generation
"""
import os
import requests
import json
import logging
from typing import Dict, Any, Optional
from flask import current_app

class LLMClient:
    """Client for communicating with LLM server"""
    
    def __init__(self):
        self.llm_url = os.getenv('LLM_SERVER_URL')
        self.api_key = os.getenv('LLM_API_KEY')
        self.model = os.getenv('LLM_MODEL', 'llama2')
        
        if not self.llm_url:
            if current_app:
                current_app.logger.warning("LLM_SERVER_URL not configured")
    
    def generate_response(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate AI response to incoming message"""
        try:
            if not self.llm_url:
                return self._get_fallback_response(message)
            
            # Prepare the prompt
            system_prompt = self._build_system_prompt(context)
            
            # Create request payload
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "max_tokens": 150,
                "temperature": 0.7,
                "stream": False
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Make request to LLM server
            response = requests.post(
                self.llm_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
                
                if current_app:
                    current_app.logger.info(f"Generated AI response: {ai_response[:50]}...")
                
                return {
                    'success': True,
                    'response': ai_response,
                    'source': 'llm_server'
                }
            else:
                if current_app:
                    current_app.logger.error(f"LLM server error: {response.status_code}")
                return self._get_fallback_response(message)
                
        except requests.exceptions.Timeout:
            if current_app:
                current_app.logger.error("LLM server timeout")
            return self._get_fallback_response(message)
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"LLM generation failed: {e}")
            return self._get_fallback_response(message)
    
    def _build_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Build system prompt for AI assistant"""
        base_prompt = """You are a helpful AI assistant responding to SMS messages. 
Keep responses short (under 160 characters), friendly, and professional. 
If someone asks for help, provide useful information.
If it's a greeting, respond warmly.
If you can't help with something, politely explain and suggest alternatives."""
        
        if context:
            profile_name = context.get('profile_name', 'Assistant')
            base_prompt += f"\nYou are responding as {profile_name}."
            
            if context.get('business_type'):
                base_prompt += f"\nYou work for a {context['business_type']} business."
        
        return base_prompt
    
    def _get_fallback_response(self, message: str) -> Dict[str, Any]:
        """Generate fallback response when LLM is unavailable"""
        message_lower = message.lower().strip()
        
        # Simple rule-based responses
        if any(greeting in message_lower for greeting in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            response = "Hello! Thanks for reaching out. How can I help you today?"
        elif any(word in message_lower for word in ['help', 'support', 'assist']):
            response = "I'm here to help! Please let me know what you need assistance with."
        elif any(word in message_lower for word in ['hours', 'open', 'schedule']):
            response = "Our typical hours are Monday-Friday 9AM-5PM. Is there something specific I can help you with?"
        elif any(word in message_lower for word in ['price', 'cost', 'rate', 'fee']):
            response = "I'd be happy to discuss pricing with you. What service are you interested in?"
        elif any(word in message_lower for word in ['location', 'address', 'where']):
            response = "I can help you with location information. What specific location details do you need?"
        elif 'thank' in message_lower:
            response = "You're welcome! Is there anything else I can help you with?"
        else:
            response = "Thank you for your message! I'll get back to you with more details soon."
        
        return {
            'success': True,
            'response': response,
            'source': 'fallback'
        }

# Global LLM client instance
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get or create LLM client instance"""
    global _llm_client
    
    if _llm_client is None:
        _llm_client = LLMClient()
    
    return _llm_client
