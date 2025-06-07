#!/usr/bin/env python3
"""
POST request test to local LLM server at 10.0.0.4:8080
"""

import requests
import json
import time
import sys

# Configuration
LLM_HOST = "10.0.0.4"
LLM_PORT = "8080"
LLM_URL = f"http://{LLM_HOST}:{LLM_PORT}"

def test_llm_post_request():
    """Test POST request to LLM server"""
    print(f"🚀 Testing POST request to {LLM_URL}")
    print("=" * 50)
    
    # Test different endpoint patterns
    endpoints = [
        "/v1/chat/completions",  # OpenAI-compatible
        "/api/generate",         # Ollama format
        "/generate",             # Simple format
        "/chat",                 # Chat format
        "/completion"            # Completion format
    ]
    
    # Test payloads for different formats
    test_payloads = {
        "/v1/chat/completions": {
            "model": "dolphin-mistral:7b",
            "messages": [
                {"role": "system", "content": "You are a helpful SMS assistant. Keep responses brief."},
                {"role": "user", "content": "Hello, how are you?"}
            ],
            "max_tokens": 50,
            "temperature": 0.7
        },
        "/api/generate": {
            "model": "dolphin-mistral:7b",
            "prompt": "Hello, respond with a brief greeting.",
            "stream": False,
            "options": {
                "temperature": 0.7,
                "max_tokens": 50
            }
        },
        "/generate": {
            "prompt": "Hello, respond with a brief greeting.",
            "max_tokens": 50,
            "temperature": 0.7
        },
        "/chat": {
            "message": "Hello, how are you?",
            "max_tokens": 50
        },
        "/completion": {
            "prompt": "Hello, respond with a brief greeting.",
            "max_length": 50
        }
    }
    
    successful_endpoint = None
    
    for endpoint in endpoints:
        print(f"\n🔍 Testing endpoint: {endpoint}")
        
        try:
            payload = test_payloads.get(endpoint, test_payloads["/generate"])
            
            print(f"   Payload: {json.dumps(payload, indent=2)[:200]}...")
            
            start_time = time.time()
            response = requests.post(
                f"{LLM_URL}{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            duration = time.time() - start_time
            
            print(f"   Status: {response.status_code}")
            print(f"   Response time: {duration:.2f}s")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"   ✅ Success! Response received")
                    
                    # Try to extract the generated text from different response formats
                    generated_text = None
                    
                    # OpenAI format
                    if 'choices' in result and result['choices']:
                        if 'message' in result['choices'][0]:
                            generated_text = result['choices'][0]['message'].get('content', '')
                        elif 'text' in result['choices'][0]:
                            generated_text = result['choices'][0]['text']
                    
                    # Ollama format
                    elif 'response' in result:
                        generated_text = result['response']
                    
                    # Simple format
                    elif 'text' in result:
                        generated_text = result['text']
                    elif 'output' in result:
                        generated_text = result['output']
                    elif 'content' in result:
                        generated_text = result['content']
                    
                    if generated_text:
                        print(f"   📝 Generated: '{generated_text.strip()[:100]}...'")
                        successful_endpoint = endpoint
                        
                        # Show full response structure for successful endpoint
                        print(f"   📋 Full response keys: {list(result.keys())}")
                        break
                    else:
                        print(f"   ⚠️  Could not extract text from response")
                        print(f"   Raw response: {json.dumps(result, indent=2)[:300]}...")
                        
                except json.JSONDecodeError:
                    print(f"   ⚠️  Response is not JSON: {response.text[:200]}...")
                    
            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found")
            elif response.status_code == 405:
                print(f"   ❌ Method not allowed")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - server may not be running")
            break
        except requests.exceptions.Timeout:
            print(f"   ❌ Request timed out")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return successful_endpoint

def test_health_endpoints():
    """Test various health check endpoints"""
    print(f"\n🏥 Testing health endpoints")
    print("=" * 30)
    
    health_endpoints = [
        "/health",
        "/api/health", 
        "/v1/health",
        "/status",
        "/api/status",
        "/",
        "/api/version",
        "/api/tags"
    ]
    
    for endpoint in health_endpoints:
        try:
            response = requests.get(f"{LLM_URL}{endpoint}", timeout=5)
            print(f"   {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"      Response: {json.dumps(data, indent=2)[:100]}...")
                except:
                    print(f"      Response: {response.text[:100]}...")
                    
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")

def create_working_example(successful_endpoint):
    """Create a working Python example"""
    if not successful_endpoint:
        print("\n❌ No working endpoint found")
        return
    
    print(f"\n📝 Working Example Code")
    print("=" * 30)
    
    example_code = f'''
import requests
import json

def send_llm_request(prompt, system_prompt=None):
    """Send request to local LLM server"""
    
    url = "{LLM_URL}{successful_endpoint}"
    '''
    
    if successful_endpoint == "/v1/chat/completions":
        example_code += '''
    payload = {
        "model": "dolphin-mistral:7b",
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        return None
'''
    elif successful_endpoint == "/api/generate":
        example_code += '''
    payload = {
        "model": "dolphin-mistral:7b", 
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 150
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
    
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        return result.get('response', '')
    else:
        return None
'''
    else:
        example_code += '''
    payload = {
        "prompt": prompt,
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        # Adjust based on actual response format
        return result.get('text') or result.get('output') or result.get('content')
    else:
        return None
'''
    
    example_code += '''

# Example usage:
if __name__ == "__main__":
    response = send_llm_request(
        "Hello, please respond briefly.",
        "You are a helpful SMS assistant."
    )
    print(f"LLM Response: {response}")
'''
    
    print(example_code)
    
    # Save to file
    with open('llm_client_example.py', 'w') as f:
        f.write(example_code)
    
    print(f"\n💾 Saved working example to: llm_client_example.py")

def main():
    """Main test function"""
    print("🧪 LLM Server POST Request Test")
    print(f"Target: {LLM_URL}")
    print("=" * 50)
    
    # Test server availability
    try:
        response = requests.get(f"{LLM_URL}/health", timeout=5)
        print(f"✅ Server reachable (health check: {response.status_code})")
    except:
        try:
            response = requests.get(f"{LLM_URL}/", timeout=5)
            print(f"✅ Server reachable (root: {response.status_code})")
        except:
            print(f"❌ Cannot reach server at {LLM_URL}")
            print("   Check if the LLM server is running on 10.0.0.4:8080")
            return
    
    # Test health endpoints
    test_health_endpoints()
    
    # Test POST requests
    successful_endpoint = test_llm_post_request()
    
    # Create working example
    create_working_example(successful_endpoint)
    
    print(f"\n🎯 Summary:")
    if successful_endpoint:
        print(f"✅ Working endpoint found: {successful_endpoint}")
        print(f"✅ Example code generated: llm_client_example.py")
    else:
        print(f"❌ No working endpoints found")
        print(f"   Check LLM server configuration")

if __name__ == "__main__":
    main()
