import requests
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMConfig:
    """LLM service configuration"""
    
    def __init__(self):
        import os
        self.base_url = os.getenv('LLM_BASE_URL', 'http://localhost:11434')
        self.model = os.getenv('LLM_MODEL', 'dolphin-mistral:latest')
        self.timeout = int(os.getenv('LLM_TIMEOUT', '30'))
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '150'))

def get_ai_response(messages: List[Dict[str, str]], personality: str = 'professional', 
                  custom_prompt: str = None) -> Optional[Dict[str, Any]]:
    """
    Generate AI response for SMS conversation
    """
    try:
        config = LLMConfig()
        
        # Build system prompt based on personality
        system_prompts = {
            'professional': "You are a professional assistant helping with business communications. Keep responses brief, helpful, and professional. Respond in 1-2 sentences maximum.",
            'friendly': "You are a friendly and warm assistant. Keep responses casual, helpful, and brief. Respond in 1-2 sentences maximum.",
            'formal': "You are a formal business assistant. Keep responses polite, concise, and professional. Respond in 1-2 sentences maximum."
        }
        
        system_prompt = custom_prompt or system_prompts.get(personality, system_prompts['professional'])
        
        # Prepare messages for LLM
        llm_messages = [
            {"role": "system", "content": system_prompt}
        ]
        llm_messages.extend(messages)
        
        # Make request to LLM service
        payload = {
            "model": config.model,
            "messages": llm_messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "max_tokens": config.max_tokens,
                "top_p": 0.9
            }
        }
        
        response = requests.post(
            f"{config.base_url}/api/chat",
            json=payload,
            timeout=config.timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_content = result.get('message', {}).get('content', '').strip()
            
            if ai_content:
                return {
                    'content': ai_content,
                    'model': config.model,
                    'confidence': 0.8,  # Default confidence
                    'generated_at': datetime.utcnow().isoformat()
                }
        
        logger.error(f"LLM request failed: {response.status_code} - {response.text}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"LLM connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"AI response generation error: {str(e)}")
        return None

def test_llm_connection() -> Dict[str, Any]:
    """Test connection to LLM service"""
    try:
        config = LLMConfig()
        
        test_payload = {
            "model": config.model,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "stream": False
        }
        
        response = requests.post(
            f"{config.base_url}/api/chat",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': 'LLM connection successful',
                'model': config.model,
                'base_url': config.base_url
            }
        else:
            return {
                'success': False,
                'error': f'LLM responded with status {response.status_code}',
                'details': response.text
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'LLM connection failed: {str(e)}'
        }