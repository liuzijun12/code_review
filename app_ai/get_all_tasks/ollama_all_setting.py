"""
Ollama Configuration and Code Analysis Module

This module provides basic Ollama configuration and code analysis functionality.
Configuration is loaded from environment variables.
"""
import os
import logging
import requests
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


# ==================== Configuration ====================

class OllamaConfig:
    """Ollama Configuration Manager - Load from environment variables"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        # Basic settings
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').strip().rstrip('/')
        
        # Model name - prioritize OLLAMA_COMMIT_ANALYSIS_MODEL, fallback to OLLAMA_MODEL
        self.model_name = (
            os.getenv('OLLAMA_COMMIT_ANALYSIS_MODEL') or 
            os.getenv('OLLAMA_MODEL') or 
            'qwen2.5-coder:7b'
        ).strip()
        
        # Timeout settings
        self.timeout = int(os.getenv('OLLAMA_TIMEOUT', '300'))
        self.connection_timeout = int(os.getenv('OLLAMA_CONNECTION_TIMEOUT', '10'))
        
        # Content limits
        self.max_code_length = int(os.getenv('OLLAMA_MAX_CODE_LENGTH', '50000'))
        self.max_prompt_length = int(os.getenv('OLLAMA_MAX_PROMPT_LENGTH', '100000'))
        
        # Analysis settings
        self.enable_streaming = os.getenv('OLLAMA_ENABLE_STREAMING', 'false').lower() == 'true'
        self.temperature = float(os.getenv('OLLAMA_TEMPERATURE', '0.7'))
        
        logger.info(f"Ollama Config: {self.base_url}, Model: {self.model_name}")
    
    def to_dict(self) -> Dict:
        """Export configuration as dictionary"""
        return {
            'base_url': self.base_url,
            'model_name': self.model_name,
            'timeout': self.timeout,
            'connection_timeout': self.connection_timeout,
            'max_code_length': self.max_code_length,
            'max_prompt_length': self.max_prompt_length,
            'enable_streaming': self.enable_streaming,
            'temperature': self.temperature
        }
    
    def __repr__(self):
        return f"OllamaConfig(base_url={self.base_url}, model={self.model_name})"


# Global configuration instance
ollama_config = OllamaConfig()


# ==================== Ollama Client ====================

class OllamaAnalysisClient:
    """Simple Ollama Client for Code Analysis"""
    
    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize Ollama client
        
        Args:
            base_url: Ollama service URL (optional, defaults to config)
            model_name: Model name (optional, defaults to config)
        """
        self.base_url = base_url or ollama_config.base_url
        self.model_name = model_name or ollama_config.model_name
        self.timeout = ollama_config.timeout
        self.connection_timeout = ollama_config.connection_timeout
        self.max_code_length = ollama_config.max_code_length
        self.temperature = ollama_config.temperature
        
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def check_connection(self) -> Dict[str, Any]:
        """
        Check Ollama service connection status
        
        Returns:
            {
                'status': 'connected' or 'error',
                'base_url': str,
                'available_models': List[str],
                'model_count': int
            }
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.connection_timeout
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                return {
                    'status': 'connected',
                    'base_url': self.base_url,
                    'available_models': [m['name'] for m in models],
                    'model_count': len(models)
                }
            else:
                return {
                    'status': 'error',
                    'base_url': self.base_url,
                    'error': f'HTTP {response.status_code}'
                }
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed: {e}")
            return {
                'status': 'error',
                'base_url': self.base_url,
                'error': 'Cannot connect to Ollama service'
            }
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return {
                'status': 'error',
                'base_url': self.base_url,
                'error': str(e)
            }
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate response from Ollama
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
        
        Returns:
            {
                'status': 'success' or 'error',
                'response': str,  # AI response
                'model': str,
                'error': str  # if error
            }
        """
        try:
            messages = []
            if system_prompt:
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            
            messages.append({
                'role': 'user',
                'content': prompt
            })
            
            payload = {
                'model': self.model_name,
                'messages': messages,
                'stream': False,
                'options': {
                    'temperature': self.temperature
                }
            }
            
            logger.info(f"Sending request to Ollama: {len(prompt)} chars")
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'response': data.get('message', {}).get('content', ''),
                    'model': data.get('model', self.model_name),
                    'done': data.get('done', True)
                }
            else:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                logger.error(f"Request failed: {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg
                }
        
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {
                'status': 'error',
                'error': 'Request timeout'
            }
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def analyze_code(
        self, 
        code: str, 
        filename: str = "code.py",
        language: str = "Python"
    ) -> Dict[str, Any]:
        """
        Analyze code using Ollama
        
        Args:
            code: Code content to analyze
            filename: File name (for context)
            language: Programming language
        
        Returns:
            Analysis result dict
        """
        # Truncate if too long
        if len(code) > self.max_code_length:
            logger.warning(f"Code truncated: {len(code)} -> {self.max_code_length}")
            code = code[:self.max_code_length] + "\n... [Content truncated]"
        
        system_prompt = "You are a senior code reviewer specializing in code quality, security, and best practices."
        
        prompt = f"""
Please review the following {language} code file: {filename}

Code:
```{language.lower()}
{code}
```

Provide a comprehensive code review covering:

1. **Code Quality**
   - Readability and maintainability
   - Naming conventions
   - Code structure

2. **Potential Issues**
   - Bugs or logic errors
   - Security vulnerabilities
   - Performance concerns

3. **Best Practices**
   - Design patterns
   - Error handling
   - Code duplication

4. **Suggestions**
   - Improvements
   - Optimizations

Please respond in Chinese with detailed analysis.
"""
        
        result = self.generate(prompt, system_prompt)
        
        if result['status'] == 'success':
            result['filename'] = filename
            result['language'] = language
            result['code_length'] = len(code)
        
        return result


# ==================== Helper Functions ====================

def get_ollama_client(base_url: Optional[str] = None, model_name: Optional[str] = None) -> OllamaAnalysisClient:
    """
    Get Ollama client instance
    
    Args:
        base_url: Ollama URL (optional)
        model_name: Model name (optional)
    
    Returns:
        OllamaAnalysisClient instance
    """
    return OllamaAnalysisClient(base_url, model_name)


def test_connection() -> Dict[str, Any]:
    """
    Test Ollama service connection
    
    Returns:
        Connection status dict
    """
    client = OllamaAnalysisClient()
    return client.check_connection()