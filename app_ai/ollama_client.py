import os
import json
import requests
from typing import Dict, List, Optional, Any
from django.conf import settings


class OllamaClient:
    """
    Ollama客户端，用于连接本地Docker中的Ollama服务
    """
    
    def __init__(self, base_url: str = None):
        """
        初始化Ollama客户端
        
        Args:
            base_url: Ollama服务的基础URL，默认从环境变量获取
        """
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.base_url = self.base_url.rstrip('/')  # 移除末尾的斜杠
        
        # 请求超时设置
        self.timeout = 120  # 120秒超时，AI推理需要更长时间
        
        # 请求头
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'CodeReview-Ollama-Client/1.0'
        }
    
    def check_connection(self) -> Dict[str, Any]:
        """
        检查Ollama服务连接状态
        
        Returns:
            dict: 连接状态信息
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
            dict: 模型列表信息
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
            dict: 拉取结果
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
    
    def chat(self, model_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        """
        与模型进行对话
        
        Args:
            model_name: 模型名称
            messages: 对话消息列表，格式: [{"role": "user", "content": "Hello"}]
            stream: 是否使用流式响应
            
        Returns:
            dict: 对话结果
        """
        try:
            payload = {
                'model': model_name,
                'messages': messages,
                'stream': stream
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
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
                    'error': f'Chat request failed: HTTP {response.status_code}',
                    'message': response.text,
                    'model': model_name
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Chat request failed: {str(e)}',
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
            dict: 生成结果
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
    
    def code_review(self, code_content: str, model_name: str = 'llama3.1:8b') -> Dict[str, Any]:
        """
        代码审查功能
        
        Args:
            code_content: 要审查的代码内容
            model_name: 使用的模型名称，默认llama2
            
        Returns:
            dict: 代码审查结果
        """
        prompt = f"""
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
"""
        
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的代码审查专家，擅长发现代码中的问题并提供改进建议。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        result = self.chat(model_name, messages)
        
        if result['status'] == 'success':
            result['review_type'] = 'code_review'
            result['code_length'] = len(code_content)
            result['model_used'] = model_name
        
        return result
    
    def explain_commit(self, commit_data: Dict[str, Any], model_name: str = 'llama3.1:8b') -> Dict[str, Any]:
        """
        解释提交内容
        
        Args:
            commit_data: 提交数据，包含提交信息和代码变更
            model_name: 使用的模型名称
            
        Returns:
            dict: 提交解释结果
        """
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
        
        prompt = f"""
请分析以下Git提交，并提供详细的解释：

提交信息: {commit_message}

文件变更:
{chr(10).join(files_info)}

请解释：
1. 这个提交做了什么？
2. 代码变更的目的和影响
3. 是否存在潜在问题
4. 建议和改进点
"""
        
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的代码审查专家，擅长分析Git提交和代码变更。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        result = self.chat(model_name, messages)
        
        if result['status'] == 'success':
            result['analysis_type'] = 'commit_explanation'
            result['commit_sha'] = commit_data.get('sha', '')
            result['files_count'] = len(files_changed)
            result['model_used'] = model_name
        
        return result
    
    def get_client_status(self) -> Dict[str, Any]:
        """
        获取客户端状态信息
        
        Returns:
            dict: 客户端状态
        """
        connection_status = self.check_connection()
        models_info = self.list_models() if connection_status['status'] == 'connected' else {'models': [], 'models_count': 0}
        
        return {
            'ollama_client': {
                'base_url': self.base_url,
                'connection_status': connection_status['status'],
                'timeout': self.timeout,
                'available_models': connection_status.get('available_models', []),
                'models_count': models_info.get('models_count', 0)
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
