"""
Ollama API客户端模块

该模块提供了与Ollama API交互的客户端实现，支持模型管理、聊天对话和代码审查等功能。
"""
import os
import time
import functools
import json
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast, TypedDict, Generator, Union
from abc import ABC, abstractmethod

import requests
from django.conf import settings

class Message(TypedDict):
    """聊天消息类型定义"""
    role: str
    content: str

class HttpClient(ABC):
    """HTTP客户端抽象接口"""
    @abstractmethod
    def get(self, url: str, headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        pass

class RequestsHttpClient(HttpClient):
    """基于requests的HTTP客户端实现"""
    def get(self, url: str, headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
        response = requests.get(url, headers=headers, timeout=timeout)
        return {
            'status_code': response.status_code,
            'json': response.json(),
            'text': response.text
        }
        
    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        response = requests.post(url, headers=headers, json=json, timeout=timeout)
        return {
            'status_code': response.status_code,
            'json': response.json(),
            'text': response.text
        }

# 定义泛型类型变量，用于装饰器返回类型
T = TypeVar('T')


class OllamaClient:
    """
    Ollama客户端，用于连接本地Docker中的Ollama服务
    """
    
    def __init__(self, base_url: Optional[str] = None, http_client: Optional[HttpClient] = None):
        """
        初始化Ollama客户端
        
        Args:
            base_url: Ollama服务的基础URL，默认从环境变量或Django settings获取
            http_client: HTTP客户端实现，默认为RequestsHttpClient
        """
        self.base_url = base_url or getattr(settings, 'OLLAMA_BASE_URL', os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
        self.base_url = self.base_url.rstrip('/')  # 移除末尾的斜杠
        
        # 从Django settings读取配置
        self.timeout = getattr(settings, 'OLLAMA_TIMEOUT', 120)  # 120秒超时
        self.max_retries = getattr(settings, 'OLLAMA_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'OLLAMA_RETRY_DELAY', 1)
        self.retry_backoff = getattr(settings, 'OLLAMA_RETRY_BACKOFF', 2)
        self.retry_status_codes = getattr(settings, 'OLLAMA_RETRY_STATUS_CODES', [408, 429, 500, 502, 503, 504])
        
        # 请求头
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': getattr(settings, 'OLLAMA_USER_AGENT', 'CodeReview-Ollama-Client/1.0')
        }
        
        # HTTP客户端实现
        self.http_client = http_client or RequestsHttpClient()
        
        # 重试异常类型
        self.retry_exceptions = (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException
        )
    
    def with_retry(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        重试装饰器，为API调用添加重试逻辑
        
        Args:
            func: 需要添加重试逻辑的函数
            
        Returns:
            Callable: 包装后的函数
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            delay = self.retry_delay
            
            for attempt in range(1, self.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # 检查是否为字典类型的结果，并且包含错误状态码
                    if isinstance(result, dict) and result.get('status') == 'error':
                        # 检查是否包含HTTP状态码
                        error_msg = result.get('error', '')
                        if any(f"HTTP {code}" in error_msg for code in self.retry_status_codes):
                            if attempt < self.max_retries:
                                time.sleep(delay)
                                delay *= self.retry_backoff
                                continue
                    
                    return result
                except self.retry_exceptions as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        delay *= self.retry_backoff
                    else:
                        # 最后一次尝试失败，返回错误信息
                        if hasattr(func, '__name__'):
                            operation = func.__name__
                        else:
                            operation = "operation"
                        
                        return cast(T, {
                            'status': 'error',
                            'error': f"{operation} failed after {self.max_retries} attempts: {str(last_exception)}",
                            'retries': self.max_retries
                        })
            
            # 这里理论上不会执行到，但为了类型检查添加
            return cast(T, {
                'status': 'error',
                'error': f"Unknown error after {self.max_retries} attempts",
                'retries': self.max_retries
            })
        
        return wrapper
    
    def check_connection(self) -> Dict[str, Any]:
        """
        检查Ollama服务连接状态
        
        Returns:
            Dict[str, Any]: 连接状态信息，包含状态码、可用模型等
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                return {
                    'status': 'connected',
                    'base_url': self.base_url,
                    'available_models': [model['name'] for model in models],
                    'models_count': len(models),
                    'connection_test': 'success'
                }
            else:
                return {
                    'status': 'error',
                    'base_url': self.base_url,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'connection_test': 'failed'
                }
                
        except requests.exceptions.ConnectionError:
            return {
                'status': 'disconnected',
                'base_url': self.base_url,
                'error': 'Cannot connect to Ollama service. Please check if Docker container is running.',
                'connection_test': 'failed',
                'troubleshooting': [
                    'Check if Docker is running: docker ps',
                    'Check if Ollama container is running: docker-compose ps',
                    'Start Ollama service: docker-compose up -d ollama',
                    'Check container logs: docker-compose logs ollama'
                ]
            }
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'base_url': self.base_url,
                'error': 'Connection timeout. Ollama service might be starting up.',
                'connection_test': 'failed'
            }
        except Exception as e:
            return {
                'status': 'error',
                'base_url': self.base_url,
                'error': f'Unexpected error: {str(e)}',
                'connection_test': 'failed'
            }
    
    def list_models(self) -> Dict[str, Any]:
        """
        获取可用的模型列表
        
        Returns:
            Dict[str, Any]: 模型列表信息，包含模型名称、大小等详细信息
        """
        return self.with_retry(self._list_models)()
    
    def _list_models(self) -> Dict[str, Any]:
        """
        获取可用的模型列表的内部实现
        
        Returns:
            Dict[str, Any]: 模型列表信息
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                model_details = []
                for model in models:
                    model_details.append({
                        'name': model.get('name', ''),
                        'size': model.get('size', 0),
                        'digest': model.get('digest', ''),
                        'modified_at': model.get('modified_at', ''),
                        'details': model.get('details', {})
                    })
                
                return {
                    'status': 'success',
                    'models': model_details,
                    'models_count': len(model_details)
                }
            else:
                return {
                    'status': 'error',
                    'error': f'Failed to fetch models: HTTP {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Failed to list models: {str(e)}'
            }
    
    def pull_model(self, model_name: str) -> Dict[str, Any]:
        """
        拉取模型
        
        Args:
            model_name: 要拉取的模型名称
            
        Returns:
            Dict[str, Any]: 拉取结果，包含状态和错误信息（如有）
        """
        return self.with_retry(self._pull_model)(model_name)
    
    def _pull_model(self, model_name: str) -> Dict[str, Any]:
        """
        拉取模型的内部实现
        
        Args:
            model_name: 要拉取的模型名称
            
        Returns:
            Dict[str, Any]: 拉取结果
        """
        try:
            payload = {'name': model_name}
            
            response = requests.post(
                f"{self.base_url}/api/pull",
                headers=self.headers,
                json=payload,
                timeout=300  # 5分钟超时，拉取模型可能需要较长时间
            )
            
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'message': f'Model {model_name} pulled successfully',
                    'model_name': model_name
                }
            else:
                return {
                    'status': 'error',
                    'error': f'Failed to pull model: HTTP {response.status_code}',
                    'message': response.text,
                    'model_name': model_name
                }
                
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'error': 'Model pull timeout (5 minutes). The operation might still be running in background.',
                'model_name': model_name
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Failed to pull model: {str(e)}',
                'model_name': model_name
            }
    
    def chat(self, model_name: str, messages: List[Message], stream: bool = False) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        与模型进行对话
        
        Args:
            model_name: 模型名称
            messages: 对话消息列表
            stream: 是否使用流式响应
            
        Returns:
            Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]: 对话结果，包含模型响应内容和元数据
        """
        return self.with_retry(self._chat)(model_name, messages, stream)
    
    def _chat(self, model_name: str, messages: List[Message], stream: bool = False) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        与模型进行对话的内部实现
        
        Args:
            model_name: 模型名称
            messages: 对话消息列表
            stream: 是否使用流式响应
            
        Returns:
            Dict[str, Any]: 对话结果
        """
        if stream:
            return self._stream_chat(model_name, messages)
            
        try:
            payload = {
                'model': model_name,
                'messages': messages,
                'stream': False
            }
            
            response = self.http_client.post(
                f"{self.base_url}/api/chat",
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response['status_code'] == 200:
                data = response['json']
                return {
                    'status': 'success',
                    'response': data.get('message', {}).get('content', ''),
                    'model': data.get('model', model_name),
                    'created_at': data.get('created_at', ''),
                    'done': data.get('done', True),
                    'total_duration': data.get('total_duration', 0),
                    'load_duration': data.get('load_duration', 0),
                    'prompt_eval_count': data.get('prompt_eval_count', 0),
                    'eval_count': data.get('eval_count', 0)
                }
            else:
                return {
                    'status': 'error',
                    'error': f'Chat request failed: HTTP {response["status_code"]}',
                    'message': response['text'],
                    'model': model_name
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Chat request failed: {str(e)}',
                'model': model_name
            }
    
    def _stream_chat(self, model_name: str, messages: List[Message]) -> Generator[Dict[str, Any], None, None]:
        """
        流式聊天实现
        
        Args:
            model_name: 模型名称
            messages: 对话消息列表
            
        Yields:
            Dict[str, Any]: 流式响应块
        """
        try:
            payload = {
                'model': model_name,
                'messages': messages,
                'stream': True
            }
            
            with requests.post(
                f"{self.base_url}/api/chat",
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
                stream=True
            ) as response:
                
                if response.status_code != 200:
                    yield {
                        'status': 'error',
                        'error': f'Stream chat failed: HTTP {response.status_code}',
                        'message': response.text,
                        'model': model_name
                    }
                    return
                
                full_response = []
                for chunk in response.iter_lines():
                    if chunk:
                        data = json.loads(chunk.decode('utf-8'))
                        full_response.append(data.get('message', {}).get('content', ''))
                        yield {
                            'status': 'success',
                            'chunk': data,
                            'model': data.get('model', model_name),
                            'done': data.get('done', False)
                        }
                
                yield {
                    'status': 'success',
                    'response': ''.join(full_response),
                    'model': model_name,
                    'done': True
                }
                
        except Exception as e:
            yield {
                'status': 'error',
                'error': f'Stream chat failed: {str(e)}',
                'model': model_name
            }
    
    def generate(self, model_name: str, prompt: str, stream: bool = False) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            model_name: 模型名称
            prompt: 输入提示
            stream: 是否使用流式响应
            
        Returns:
            Dict[str, Any]: 生成结果，包含生成的文本和相关元数据
        """
        return self.with_retry(self._generate)(model_name, prompt, stream)
    
    def _generate(self, model_name: str, prompt: str, stream: bool = False) -> Dict[str, Any]:
        """
        生成文本的内部实现
        
        Args:
            model_name: 模型名称
            prompt: 输入提示
            stream: 是否使用流式响应
            
        Returns:
            Dict[str, Any]: 生成结果
        """
        try:
            payload = {
                'model': model_name,
                'prompt': prompt,
                'stream': stream
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'response': data.get('response', ''),
                    'model': data.get('model', model_name),
                    'created_at': data.get('created_at', ''),
                    'done': data.get('done', True),
                    'context': data.get('context', []),
                    'total_duration': data.get('total_duration', 0),
                    'load_duration': data.get('load_duration', 0),
                    'prompt_eval_count': data.get('prompt_eval_count', 0),
                    'eval_count': data.get('eval_count', 0)
                }
            else:
                return {
                    'status': 'error',
                    'error': f'Generate request failed: HTTP {response.status_code}',
                    'message': response.text,
                    'model': model_name
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Generate request failed: {str(e)}',
                'model': model_name
            }
    
    def code_review(self, code_content: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        代码审查功能
        
        Args:
            code_content: 要审查的代码内容
            model_name: 使用的模型名称，默认从settings获取
            
        Returns:
            Dict[str, Any]: 代码审查结果，包含分析和建议
        """
        model_name = model_name or getattr(settings, 'OLLAMA_CODE_REVIEW_MODEL', 'llama3.1:8b')
        if not model_name:
            raise ValueError("Model name must be specified either directly or in settings")
        """
        代码审查功能
        
        Args:
            code_content: 要审查的代码内容
            model_name: 使用的模型名称，默认从settings获取
            
        Returns:
            Dict[str, Any]: 代码审查结果，包含分析和建议
        """
        model_name = model_name or getattr(settings, 'OLLAMA_CODE_REVIEW_MODEL', 'llama3.1:8b')
        if not model_name:
            return {
                'status': 'error',
                'error': 'Model name must be specified either directly or in settings'
            }
            
        prompt_template = getattr(settings, 'OLLAMA_CODE_REVIEW_PROMPT', """
请对以下代码进行详细的代码审查，包括但不限于：

1. 代码质量和风格
2. 潜在的bug和安全问题
3. 性能优化建议
4. 最佳实践建议
5. 可维护性和可读性

代码内容：
```
{code_content}
```

请提供详细的分析和具体的改进建议。
""")
        
        prompt = prompt_template.format(code_content=code_content)
        
        messages: List[Message] = [
            {
                "role": "system",
                "content": "你是一个专业的代码审查专家，擅长发现代码中的问题并提供改进建议。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        result = self.chat(model_name, messages, stream=False)
        
        # 处理可能的返回类型
        if isinstance(result, dict):
            if result.get('status') == 'success':
                result['review_type'] = 'code_review'
                result['code_length'] = len(code_content)
                result['model_used'] = model_name
            return result
        elif hasattr(result, '__iter__') and not isinstance(result, dict):  # Generator case
            # 收集所有流式响应
            full_result = None
            for chunk in result:
                if isinstance(chunk, dict) and chunk.get('done'):
                    full_result = chunk
                    break
            
            if full_result and full_result.get('status') == 'success':
                full_result['review_type'] = 'code_review'
                full_result['code_length'] = len(code_content)
                full_result['model_used'] = model_name
                return full_result
            
            return {
                'status': 'error',
                'error': 'Failed to collect stream response'
            }
        
        return {
            'status': 'error',
            'error': 'Unexpected response type from chat'
        }
        
        return result
    
    def explain_commit(self, commit_data: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
        if not model_name:
            model_name = getattr(settings, 'OLLAMA_COMMIT_EXPLAIN_MODEL', 'llama3.1:8b')
            if not model_name:
                raise ValueError("Model name must be specified either directly or in settings")
        """
        解释提交内容
        
        Args:
            commit_data: 提交数据，包含提交信息和代码变更
            model_name: 使用的模型名称，默认从settings获取
            
        Returns:
            Dict[str, Any]: 提交解释结果，包含分析和建议
        """
        model_name = model_name or getattr(settings, 'OLLAMA_COMMIT_EXPLAIN_MODEL', 'llama3.1:8b')
        if not model_name:
            raise ValueError("Model name must be specified either directly or in settings")
        commit_message = commit_data.get('message', '')
        files_changed = commit_data.get('files', [])
        
        files_info = []
        for file_data in files_changed:
            files_info.append(f"文件: {file_data.get('filename', '')}")
            files_info.append(f"状态: {file_data.get('status', '')}")
            files_info.append(f"修改: +{file_data.get('additions', 0)} -{file_data.get('deletions', 0)}")
            if 'patch' in file_data:
                files_info.append(f"代码变更:\n{file_data['patch'][:500]}...")  # 限制长度
            files_info.append("---")
        
        prompt_template = getattr(settings, 'OLLAMA_COMMIT_EXPLAIN_PROMPT', """
# Git提交分析请求

## 提交基本信息
- 提交信息: {commit_message}
- 变更文件数: {files_count}

## 详细变更内容
{files_info}

## 分析要求
作为一位拥有8年经验的高级开发工程师和代码审查专家，请对此次代码变更进行全面、专业的分析...
""")
        
        prompt = prompt_template.format(
            commit_message=commit_message,
            files_count=len(files_changed),
            files_info='\n'.join(files_info)
        )
        
        messages: List[Message] = [
            {
                "role": "system", 
                "content": "你是一个专业的代码审查专家，擅长分析Git提交和代码变更。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        chat_result = self.chat(model_name, messages)
        
        # 处理可能的返回类型
        if isinstance(chat_result, dict):
            if chat_result.get('status') == 'success':
                chat_result['analysis_type'] = 'commit_explanation'
                chat_result['commit_sha'] = commit_data.get('sha', '')
                chat_result['files_count'] = len(files_changed)
            return chat_result
        elif hasattr(chat_result, '__iter__') and not isinstance(chat_result, dict):  # Generator case
            # 收集所有流式响应
            full_result = None
            for chunk in chat_result:
                if isinstance(chunk, dict) and chunk.get('done'):
                    full_result = chunk
                    break
            
            if full_result and full_result.get('status') == 'success':
                full_result['analysis_type'] = 'commit_explanation'
                full_result['commit_sha'] = commit_data.get('sha', '')
                full_result['files_count'] = len(files_changed)
                return full_result
            
            return {
                'status': 'error',
                'error': 'Failed to collect stream response'
            }
        
        return {
            'status': 'error',
            'error': 'Unexpected response type from chat'
        }
        result['model_used'] = model_name
        
        return result
    
    def get_client_status(self) -> Dict[str, Any]:
        """
        获取客户端状态信息
        
        Returns:
            Dict[str, Any]: 客户端状态，包含连接状态、可用模型和功能列表
        """
        connection_status = self.check_connection()
        models_info = self.list_models() if connection_status['status'] == 'connected' else {'models': [], 'models_count': 0}
        
        return {
            'ollama_client': {
                'base_url': self.base_url,
                'connection_status': connection_status['status'],
                'timeout': self.timeout,
                'available_models': connection_status.get('available_models', []),
                'models_count': models_info.get('models_count', 0),
                'retry_config': {
                    'max_retries': self.max_retries,
                    'retry_delay': self.retry_delay,
                    'retry_backoff': self.retry_backoff,
                    'retry_status_codes': self.retry_status_codes
                }
            },
            'connection_details': connection_status,
            'models_details': models_info.get('models', []),
            'capabilities': [
                'code_review',
                'commit_explanation', 
                'text_generation',
                'chat_conversation',
                'model_management'
            ]
        }


# 创建全局实例
ollama_client = OllamaClient()
