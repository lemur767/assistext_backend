# app/utils/ollama_client.py
import os
import requests
import json
import logging
from typing import Dict, Any, Optional, List
from flask import current_app

class OllamaClient:
    """Client for communicating with Ollama LLM server"""
    
    def __init__(self, host: str = None, port: int = None, model: str = None):
        self.host = host or os.getenv('LLM_SERVER_IP', '10.0.0.4')
        self.port = port or int(os.getenv('LLM_SERVER_PORT', '8080'))
        self.model = model or os.getenv('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
        self.base_url = f"http://{self.host}:{self.port}"
        self.timeout = int(os.getenv('LLM_TIMEOUT', '30'))
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def generate_sms_response(self, incoming_message: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Generate AI response specifically for SMS messages"""
        try:
            # Build system prompt for SMS context
            system_prompt = self._build_sms_system_prompt(context)
            
            # Create prompt for SMS response
            prompt = f"""System: {system_prompt}

User message: {incoming_message}

Respond naturally and helpfully. Keep response under 160 characters for SMS."""

            # Make request to Ollama
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": float(os.getenv('LLM_TEMPERATURE', '0.7')),
                        "num_predict": int(os.getenv('LLM_MAX_TOKENS', '150')),
                        "top_k": 40,
                        "top_p": 0.9,
                        "stop": ["\n\n", "User:", "System:"]
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '').strip()
                
                # Clean up response for SMS
                ai_response = self._clean_sms_response(ai_response)
                
                self.logger.info(f"LLM response generated: {len(ai_response)} chars")
                return ai_response
            else:
                self.logger.error(f"LLM server error: {response.status_code} - {response.text}")
                return self._get_fallback_response(incoming_message)
                
        except requests.exceptions.Timeout:
            self.logger.error("LLM request timed out")
            return self._get_fallback_response(incoming_message)
        except Exception as e:
            self.logger.error(f"LLM error: {str(e)}")
            return self._get_fallback_response(incoming_message)
    
    def _build_sms_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Build system prompt for SMS responses"""
        base_prompt = """You are a helpful AI assistant responding to text messages. 
        - Keep responses short and conversational
        - Be friendly and professional
        - Maximum 160 characters
        - Don't use emojis unless asked
        - Provide direct, helpful answers"""
        
        if context:
            if context.get('user_name'):
                base_prompt += f"\n- User's name is {context['user_name']}"
            if context.get('business_context'):
                base_prompt += f"\n- Business context: {context['business_context']}"
        
        return base_prompt
    
    def _clean_sms_response(self, response: str) -> str:
        """Clean and format response for SMS"""
        # Remove any system artifacts
        response = response.replace("System:", "").replace("User:", "").strip()
        
        # Truncate to SMS length
        if len(response) > 160:
            response = response[:157] + "..."
        
        return response
    
    def _get_fallback_response(self, message: str) -> str:
        """Fallback response when LLM is unavailable"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! How can I help you today?"
        elif any(word in message_lower for word in ['help', 'support']):
            return "I'm here to help! What can I assist you with?"
        elif any(word in message_lower for word in ['price', 'cost', 'rate']):
            return "I'd be happy to discuss pricing. What service interests you?"
        elif 'thank' in message_lower:
            return "You're welcome! Anything else I can help with?"
        else:
            return "Thanks for your message! I'll get back to you soon."
    
    def health_check(self) -> Dict[str, Any]:
        """Check if LLM server is healthy"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "Say OK",
                    "stream": False,
                    "options": {"num_predict": 5}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "OK" in result.get('response', ''):
                    return {"status": "healthy", "model": self.model}
            
            return {"status": "unhealthy", "error": "Generation test failed"}
            
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

# Global client instance
_ollama_client = None

def get_ollama_client() -> OllamaClient:
    """Get global Ollama client instance"""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client

def generate_sms_response(message: str, context: Dict[str, Any] = None) -> str:
    """Generate SMS response using Ollama"""
    client = get_ollama_client()
    return client.generate_sms_response(message, context) or "I'm here to help!"