"""
Ollama/Dolphin Mistral LLM Client for SMS Response Generation
Optimized for dolphin-mistral:7b-v2.8 model
"""
import os
import requests
import json
import logging
from typing import Dict, Any, Optional
from flask import current_app

class OllamaLLMClient:
    """Client for communicating with Ollama running Dolphin Mistral"""
    
    def __init__(self):
        self.host = os.getenv('LLM_SERVER_IP', '10.0.0.4')
        self.port = os.getenv('LLM_SERVER_PORT', '8080')  
        self.base_url = f"http://{self.host}:{self.port}"
        self.model = os.getenv('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
        self.timeout = int(os.getenv('LLM_TIMEOUT', '30'))
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '150'))
        self.temperature = float(os.getenv('LLM_TEMPERATURE', '0.7'))
        
        # Ollama-specific endpoints
        self.generate_endpoint = f"{self.base_url}/api/generate"
        self.chat_endpoint = f"{self.base_url}/api/chat"
        
        if current_app:
            current_app.logger.info(f"Ollama LLM Client initialized: {self.base_url} - {self.model}")
    
    def generate_sms_response(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate AI response for SMS using Ollama/Dolphin Mistral
        
        Args:
            message: Incoming SMS message
            context: User/business context
            
        Returns:
            Dict with response and metadata
        """
        try:
            if not message or not message.strip():
                return self._get_fallback_response("empty_message")
            
            # Build the prompt specifically for Dolphin Mistral
            prompt = self._build_dolphin_mistral_prompt(message, context)
            
            if current_app:
                current_app.logger.info(f"Generating response for: '{message[:50]}...'")
            
            # Try chat endpoint first (preferred for conversation)
            response = self._try_chat_endpoint(prompt, context)
            if response['success']:
                return response
            
            # Fallback to generate endpoint
            response = self._try_generate_endpoint(prompt, context)
            if response['success']:
                return response
            
            # If both fail, return fallback
            return self._get_fallback_response("llm_failed")
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"LLM generation error: {str(e)}")
            return self._get_fallback_response("exception", str(e))
    
    def _try_chat_endpoint(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Try using Ollama's chat endpoint (preferred for conversation)"""
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": self._get_system_prompt(context)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "stop": ["\n\n", "User:", "Human:", "Assistant:"]
                }
            }
            
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'message' in result and 'content' in result['message']:
                    ai_response = result['message']['content'].strip()
                    cleaned_response = self._clean_sms_response(ai_response)
                    
                    if current_app:
                        current_app.logger.info(f"Chat endpoint success: '{cleaned_response[:50]}...'")
                    
                    return {
                        'success': True,
                        'response': cleaned_response,
                        'source': 'ollama_chat',
                        'model': self.model,
                        'endpoint': 'chat'
                    }
                
            if current_app:
                current_app.logger.warning(f"Chat endpoint failed: {response.status_code}")
            return {'success': False, 'error': f"Chat endpoint failed: {response.status_code}"}
            
        except requests.exceptions.Timeout:
            if current_app:
                current_app.logger.warning("Chat endpoint timeout")
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            if current_app:
                current_app.logger.warning(f"Chat endpoint error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _try_generate_endpoint(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to Ollama's generate endpoint"""
        try:
            # Build full prompt for generate endpoint
            full_prompt = self._build_full_prompt_for_generate(prompt, context)
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "stop": ["\n\n", "User:", "Human:"]
                }
            }
            
            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'response' in result:
                    ai_response = result['response'].strip()
                    cleaned_response = self._clean_sms_response(ai_response)
                    
                    if current_app:
                        current_app.logger.info(f"Generate endpoint success: '{cleaned_response[:50]}...'")
                    
                    return {
                        'success': True,
                        'response': cleaned_response,
                        'source': 'ollama_generate',
                        'model': self.model,
                        'endpoint': 'generate'
                    }
            
            if current_app:
                current_app.logger.error(f"Generate endpoint failed: {response.status_code}")
            return {'success': False, 'error': f"Generate endpoint failed: {response.status_code}"}
            
        except requests.exceptions.Timeout:
            if current_app:
                current_app.logger.error("Generate endpoint timeout")
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Generate endpoint error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _build_dolphin_mistral_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build prompt optimized for Dolphin Mistral model"""
        context = context or {}
        
        # Dolphin Mistral responds well to clear, direct prompts
        user_message = message.strip()
        
        # Keep it simple for SMS - just the user's message
        return user_message
    
    def _get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get system prompt for Dolphin Mistral"""
        context = context or {}
        
        company_name = context.get('company_name', 'our business')
        business_type = context.get('business_type', 'customer service')
        
        return f"""You are a helpful AI assistant for {company_name} ({business_type}).

IMPORTANT SMS GUIDELINES:
- Keep responses under 160 characters
- Be professional, friendly, and helpful
- Give direct, actionable responses
- Use natural, conversational language
- No emojis unless the user asks for them

Respond to the customer's message in a helpful and professional manner."""
    
    def _build_full_prompt_for_generate(self, message: str, context: Dict[str, Any]) -> str:
        """Build full prompt for the generate endpoint"""
        context = context or {}
        
        system_prompt = self._get_system_prompt(context)
        
        full_prompt = f"""{system_prompt}

Customer message: {message}

Your response:"""
        
        return full_prompt
    
    def _clean_sms_response(self, response: str) -> str:
        """Clean and optimize response for SMS"""
        if not response:
            return "Thank you for your message. How can I help you?"
        
        # Remove common AI prefixes
        prefixes_to_remove = [
            "Assistant:", "AI:", "Response:", "Your response:", 
            "As an AI", "I'm an AI", "As an assistant"
        ]
        
        cleaned = response.strip()
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
                if cleaned.startswith(':'):
                    cleaned = cleaned[1:].strip()
        
        # Ensure it fits in SMS (160 chars)
        if len(cleaned) > 160:
            # Try to cut at sentence boundary
            sentences = cleaned.split('. ')
            if len(sentences) > 1 and len(sentences[0]) <= 157:
                cleaned = sentences[0] + '.'
            else:
                # Hard cut with ellipsis
                cleaned = cleaned[:157] + '...'
        
        # Ensure proper punctuation
        if cleaned and not cleaned.endswith(('.', '!', '?')):
            cleaned += '.'
        
        return cleaned
    
    def _get_fallback_response(self, reason: str, error: str = None) -> Dict[str, Any]:
        """Generate fallback response when LLM fails"""
        
        fallback_responses = {
            'empty_message': "Hi! How can I help you today?",
            'llm_failed': "Thank you for your message. I'm here to help!",
            'timeout': "I received your message. Please give me a moment to respond.",
            'exception': "Thank you for contacting us. We'll get back to you shortly.",
            'connection_error': "Thank you for your message. I'm processing your request."
        }
        
        response = fallback_responses.get(reason, 
            "Thank you for your message. How can I assist you?")
        
        if current_app:
            current_app.logger.info(f"Using fallback response: {reason}")
        
        return {
            'success': True,
            'response': response,
            'source': 'fallback',
            'reason': reason,
            'error': error
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check if Ollama server is healthy"""
        try:
            # Try a simple generation request
            payload = {
                "model": self.model,
                "prompt": "Hello",
                "stream": False,
                "options": {"num_predict": 10}
            }
            
            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'status': 'healthy',
                    'model': self.model,
                    'endpoint': self.base_url
                }
            else:
                return {
                    'success': False,
                    'status': 'unhealthy',
                    'error': f"HTTP {response.status_code}",
                    'endpoint': self.base_url
                }
                
        except Exception as e:
            return {
                'success': False,
                'status': 'unhealthy',
                'error': str(e),
                'endpoint': self.base_url
            }

# Global instance
_ollama_client = None

def get_ollama_llm_client() -> OllamaLLMClient:
    """Get the global Ollama LLM client instance"""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaLLMClient()
    return _ollama_client