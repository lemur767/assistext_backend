import requests
import json
from typing import Dict, List, Optional
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with your local LLM server."""
    
    def __init__(self):
        """Initialize LLM service with configuration."""
        self.llm_endpoint = current_app.config.get('LLM_ENDPOINT', 'http://10.0.0.4:8080')
        self.model_name = current_app.config.get('LLM_MODEL', 'dolphin-mistral:7b')
        self.timeout = current_app.config.get('LLM_TIMEOUT', 30)
        self.max_tokens = current_app.config.get('LLM_MAX_TOKENS', 150)
        
    def generate_response(self, profile, message: str, sender_number: str,
                         conversation_history: List = None) -> Optional[str]:
        """
        Generate AI response for an incoming message.
        
        Args:
            profile: Profile object for the recipient
            message: Incoming message text
            sender_number: Phone number of sender
            conversation_history: Recent conversation history
            
        Returns:
            Generated response text or None if failed
        """
        try:
            # Prepare the prompt
            prompt = self._create_prompt(profile, message, sender_number, conversation_history)
            
            # Format request for your LLM server
            request_data = self._format_llm_request(prompt)
            
            # Make request to LLM
            logger.info(f"Sending request to LLM: {self.llm_endpoint}")
            response = requests.post(
                f"{self.llm_endpoint}/api/generate",
                json=request_data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"LLM request failed with status {response.status_code}: {response.text}")
                return None
            
            # Parse response (adjust based on your LLM server format)
            result = response.json()
            generated_text = self._extract_response_text(result)
            
            # Post-process the response
            formatted_response = self._post_process_response(generated_text, profile)
            
            logger.info(f"Successfully generated LLM response")
            return formatted_response
            
        except requests.exceptions.Timeout:
            logger.error("LLM request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LLM generation: {str(e)}", exc_info=True)
            return None
    
    def _create_prompt(self, profile, message: str, sender_number: str,
                      conversation_history: List = None) -> str:
        """Create a properly formatted prompt for the LLM."""
        from app.models.client import Client
        from app.models.text_example import TextExample
        
        # Get client information
        client = Client.query.filter_by(phone_number=sender_number).first()
        client_name = client.name if client and client.name else "the client"
        
        # Get examples of profile's texting style
        examples = TextExample.query.filter_by(profile_id=profile.id).order_by(
            TextExample.timestamp.desc()
        ).limit(5).all()
        
        # Build the prompt
        
        prompt = f"""You are {profile.name}, An escort.  Respond concisely, flirty and seductive.  Use 1 Emoji.  If the key word "rates?" is in the text use 
                            IMPORTANT RULES:
                            1. Keep responses brief (1-3 sentences max)
                            2. Match the texting style shown in examples
                            3. NEVER mention explicit services or prices
                            4. Don't reveal you're an AI
                            5. Be friendly but professional
                            6. If asked about sensitive topics, be vague or redirect

                            PROFILE INFO:
                            - Name: {profile.name}
                            - Description: {profile.description or 'Not provided'}

                            CLIENT INFO:
                            - Phone: {sender_number}
                            - Name: {client_name}
                            """

        # Add client notes if available
        if client and client.notes:
            prompt += f"- Notes: {client.notes}\n"
        
        # Add texting style examples
        if examples:
            prompt += "\nEXAMPLES OF MY TEXTING STYLE:\n"
            for example in examples:
                sender = "Client" if example.is_incoming else "Me"
                prompt += f"{sender}: {example.content}\n"
        
        # Add conversation history
        if conversation_history:
            prompt += "\nRECENT CONVERSATION:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                sender = "Client" if msg.is_incoming else "Me"
                prompt += f"{sender}: {msg.content}\n"
        
        # Add the current message
        prompt += f"\nCURRENT MESSAGE FROM CLIENT:\n{message}\n\nYOUR RESPONSE:"
        
        return prompt
    
    def _format_llm_request(self, prompt: str) -> Dict:
        """Format the request for your specific LLM server."""
        # Example format for Ollama
        return {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": self.max_tokens,
                "stop": ["\n", "Client:", "Me:"]
            }
        }
    
    def _extract_response_text(self, llm_response: Dict) -> str:
        """Extract the generated text from LLM response."""
        # Adjust based on your LLM server response format
        if "response" in llm_response:
            return llm_response["response"].strip()
        elif "text" in llm_response:
            return llm_response["text"].strip()
        elif "completion" in llm_response:
            return llm_response["completion"].strip()
        else:
            # Handle other formats
            return str(llm_response).strip()
    
    def _post_process_response(self, response: str, profile) -> str:
        """Post-process the LLM response for quality and safety."""
        # Remove any unwanted prefixes/suffixes
        response = response.replace("Me:", "").replace("Client:", "").strip()
        
        # Remove quotation marks if the whole message is quoted
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        # Ensure it's not too long
        if len(response) > 160:
            # Split at sentence boundary if possible
            sentences = response.split('. ')
            if len(sentences) > 1:
                response = sentences[0] + '.'
            else:
                response = response[:157] + "..."
        
        # Check for and remove any explicit content
        response = self._sanitize_response(response)
        
        return response
    
    def _sanitize_response(self, response: str) -> str:
        """Remove or flag any inappropriate content from the response."""
        # List of patterns to avoid
        avoid_patterns = [
            r'\$\d+',  # Prices
            r'\b(meet|appointment|date|location)\b',  # Meeting references
            r'\b(service|offer|provide)\b',  # Service references
        ]
        
        # Check for problematic patterns
        import re
        for pattern in avoid_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                # Return a safe generic response
                return "Let's chat more about this!"
        
        return response


# Alternative implementation for different LLM servers
class OpenAICompatibleLLMService(LLMService):
    """For LLM servers that use OpenAI-compatible API."""
    
    def _format_llm_request(self, prompt: str) -> Dict:
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
            "stop": ["\n", "Client:", "Me:"]
        }
    
    def generate_response(self, profile, message: str, sender_number: str,
                         conversation_history: List = None) -> Optional[str]:
        try:
            prompt = self._create_prompt(profile, message, sender_number, conversation_history)
            request_data = self._format_llm_request(prompt)
            
            response = requests.post(
                f"{self.llm_endpoint}/v1/chat/completions",
                json=request_data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"LLM request failed: {response.text}")
                return None
            
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"]
            
            return self._post_process_response(generated_text, profile)
            
        except Exception as e:
            logger.error(f"Error with OpenAI-compatible LLM: {str(e)}")
            return None