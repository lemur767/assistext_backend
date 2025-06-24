# app/utils/ollama_helpers.py
import requests
import logging
from typing import Dict, List, Optional
import json
import time

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with local Ollama LLM server"""
    
    def __init__(self, host: str = "10.0.0.4", port: int = 8080, model: str = "dolphin-mistral:7b"):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.timeout = 30
        
    def is_available(self) -> bool:
        """Check if Ollama server is available"""
        # Try multiple health check endpoints
        health_endpoints = ["/health", "/api/health", "/v1/health", "/status", "/"]
        
        for endpoint in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                continue
        
        # If no health endpoint works, try the generation endpoint
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "test"}]},
                timeout=5
            )
            return response.status_code in [200, 400, 422]  # 400/422 means endpoint exists but bad request
        except Exception as e:
            logger.error(f"Ollama server not available: {e}")
            return False
    
    def get_models(self) -> List[str]:
        """Get list of available models"""
        # Try different endpoints for getting models
        model_endpoints = ["/api/tags", "/v1/models", "/models"]
        
        for endpoint in model_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different response formats
                    if 'models' in data:
                        if isinstance(data['models'], list):
                            # Ollama format: [{"name": "model:tag", ...}, ...]
                            return [model.get('name', model.get('id', str(model))) 
                                   for model in data['models']]
                    elif 'data' in data:
                        # OpenAI format: {"data": [{"id": "model-name", ...}, ...]}
                        return [model.get('id', model.get('name', str(model))) 
                               for model in data['data']]
                    elif isinstance(data, list):
                        # Simple list format
                        return [str(model) for model in data]
                        
            except Exception as e:
                logger.debug(f"Error checking {endpoint}: {e}")
                continue
        
        logger.warning("Could not retrieve models from any endpoint")
        return []
    
    def model_exists(self, model_name: str = None) -> bool:
        """Check if a specific model exists"""
        model_to_check = model_name or self.model
        models = self.get_models()
        
        # Exact match
        if model_to_check in models:
            return True
        
        # Partial match for different tag formats
        for model in models:
            if model_to_check.split(':')[0] in model:
                return True
        
        return False
    
    def pull_model(self, model_name: str = None) -> bool:
        """Pull a model from Ollama registry"""
        model_to_pull = model_name or self.model
        
        try:
            logger.info(f"Pulling model: {model_to_pull}")
            
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_to_pull},
                stream=True,
                timeout=300  # 5 minutes for model download
            )
            
            if response.status_code == 200:
                # Stream the progress
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get('status', '')
                            if 'pulling' in status.lower():
                                logger.info(f"Pulling: {status}")
                            elif 'success' in status.lower():
                                logger.info("Model pulled successfully")
                                return True
                        except json.JSONDecodeError:
                            continue
                return True
            else:
                logger.error(f"Failed to pull model: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return False
    
    def generate_text(self, prompt: str, system_prompt: str = None, **kwargs) -> Optional[str]:
        """Generate text using the local LLM"""
        try:
            # Try OpenAI-compatible endpoint first
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            openai_payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": kwargs.get('max_tokens', 150),
                "temperature": kwargs.get('temperature', 0.7),
                "top_p": kwargs.get('top_p', 0.9),
                "stop": kwargs.get('stop', [])
            }
            
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=openai_payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and result['choices']:
                    message = result['choices'][0].get('message', {})
                    return message.get('content', '').strip()
            
            # Fallback to Ollama format
            ollama_payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "max_tokens": kwargs.get('max_tokens', 150),
                    "top_p": kwargs.get('top_p', 0.9),
                    "stop": kwargs.get('stop', [])
                }
            }
            
            if system_prompt:
                ollama_payload["system"] = system_prompt
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=ollama_payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            
            # Try simple generation endpoint
            simple_payload = {
                "prompt": prompt,
                "max_tokens": kwargs.get('max_tokens', 150),
                "temperature": kwargs.get('temperature', 0.7)
            }
            
            for endpoint in ["/generate", "/completion"]:
                try:
                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        json=simple_payload,
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Try different response key names
                        for key in ['text', 'response', 'output', 'content', 'completion']:
                            if key in result:
                                return result[key].strip()
                
                except Exception:
                    continue
            
            logger.error(f"All generation endpoints failed")
            return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Generation timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            return None
    
    def chat_completion(self, messages: List[Dict], **kwargs) -> Optional[str]:
        """Generate chat completion (OpenAI-style interface)"""
        try:
            # Convert OpenAI-style messages to Ollama format
            system_prompt = None
            conversation = []
            
            for message in messages:
                role = message.get('role')
                content = message.get('content')
                
                if role == 'system':
                    system_prompt = content
                elif role == 'user':
                    conversation.append(f"User: {content}")
                elif role == 'assistant':
                    conversation.append(f"Assistant: {content}")
            
            # Combine conversation into a single prompt
            if conversation:
                prompt = "\n".join(conversation) + "\nAssistant:"
            else:
                prompt = messages[-1].get('content', '') if messages else ""
            
            return self.generate_text(prompt, system_prompt, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            return None
    
    def health_check(self) -> Dict:
        """Comprehensive health check of the LLM service"""
        health = {
            "status": "unhealthy",
            "server_available": False,
            "model_available": False,
            "generation_working": False,
            "response_time_ms": None,
            "error": None
        }
        
        try:
            # Check server availability
            start_time = time.time()
            if not self.is_available():
                health["error"] = "Server not reachable"
                return health
            
            health["server_available"] = True
            
            # Check model availability
            if not self.model_exists():
                health["error"] = f"Model {self.model} not available"
                return health
            
            health["model_available"] = True
            
            # Test text generation
            test_response = self.generate_text(
                "Respond with exactly one word: 'OK'",
                temperature=0.1,
                max_tokens=5
            )
            
            if test_response and 'ok' in test_response.lower():
                health["generation_working"] = True
                health["status"] = "healthy"
            else:
                health["error"] = "Generation test failed"
            
            health["response_time_ms"] = int((time.time() - start_time) * 1000)
            
        except Exception as e:
            health["error"] = str(e)
        
        return health


# Global client instance
_ollama_client = None

def get_ollama_client() -> OllamaClient:
    """Get global Ollama client instance"""
    global _ollama_client
    if _ollama_client is None:
        import os
        
        host = os.getenv('LOCAL_LLM_HOST', '10.0.0.4')
        port = int(os.getenv('LOCAL_LLM_PORT', '8080'))  # Changed from 11434 to 8080
        model = os.getenv('LOCAL_LLM_MODEL', 'dolphin-mistral:7b')
        
        _ollama_client = OllamaClient(host=host, port=port, model=model)
    
    return _ollama_client

def generate_ai_response(prompt: str, system_prompt: str = None, **kwargs) -> Optional[str]:
    """Simple function to generate AI response using local LLM"""
    client = get_ollama_client()
    return client.generate_text(prompt, system_prompt, **kwargs)

def chat_completion(messages: List[Dict], **kwargs) -> Optional[str]:
    """OpenAI-compatible chat completion using local LLM"""
    client = get_ollama_client()
    return client.chat_completion(messages, **kwargs)

def is_llm_available() -> bool:
    """Quick check if LLM is available"""
    client = get_ollama_client()
    return client.is_available() and client.model_exists()

def get_llm_health() -> Dict:
    """Get LLM health status"""
    client = get_ollama_client()
    return client.health_check()
