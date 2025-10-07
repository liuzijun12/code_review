import os
import json
import requests
import time
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from .config import ollama_config

# 创建logger实例
logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Ollama客户端，用于连接本地Docker中的Ollama服务
    集成配置管理、重试机制、错误处理等功能
    """
    
    def __init__(self, base_url: str = None):
        """
        初始化Ollama客户端
        
        Args:
            base_url: Ollama服务的基础URL，默认从配置获取
        """
        # 获取配置
        self.config = ollama_config.get_config()
        
        # 设置基础URL
        self.base_url = base_url or self.config.base_url
        self.base_url = self.base_url.rstrip('/')  # 移除末尾的斜杠
        
        # 超时设置
        self.connection_timeout = self.config.connection_timeout
        self.request_timeout = self.config.request_timeout
        self.model_pull_timeout = self.config.model_pull_timeout
        
        # 重试配置
        self.max_retries = self.config.max_retries
        self.retry_delay = self.config.retry_delay
        self.retry_backoff_factor = self.config.retry_backoff_factor
        
        # 请求头
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'CodeReview-Ollama-Client/2.0'
        }
        
        # 初始化日志
        if self.config.debug_mode:
            logger.info(f"初始化Ollama客户端: {self.base_url}")
            logger.debug(f"配置: {ollama_config.to_dict()}")
    
    def _make_request_with_retry(self, method: str, url: str, timeout: int = None, **kwargs) -> requests.Response:
        """
        带重试机制的请求方法
        
        Args:
            method: HTTP方法
            url: 请求URL
            timeout: 超时时间
            **kwargs: 其他请求参数
            
        Returns:
            requests.Response: 响应对象
            
        Raises:
            requests.RequestException: 请求失败
        """
        timeout = timeout or self.request_timeout
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if self.config.log_requests:
                    logger.debug(f"发送请求: {method} {url} (尝试 {attempt + 1}/{self.max_retries + 1})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    timeout=timeout,
                    **kwargs
                )
                
                if self.config.log_requests:
                    logger.debug(f"响应状态: {response.status_code}")
                
                return response
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.retry_backoff_factor ** attempt)
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}, {delay:.1f}秒后重试")
                    time.sleep(delay)
                else:
                    logger.error(f"请求最终失败: {e}")
        
        raise last_exception
    
    def check_connection(self) -> Dict[str, Any]:
        """
        检查Ollama服务连接状态
        
        Returns:
            dict: 连接状态信息
        """
        try:
            response = self._make_request_with_retry(
                method='GET',
                url=f"{self.base_url}/api/tags",
                timeout=self.connection_timeout
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                result = {
                    'status': 'connected',
                    'base_url': self.base_url,
                    'available_models': [model['name'] for model in models],
                    'models_count': len(models),
                    'connection_test': 'success',
                    'config_loaded': True,
                    'default_models': {
                        'chat': self.config.default_chat_model,
                        'code_review': self.config.default_code_review_model,
                        'commit_analysis': self.config.default_commit_analysis_model
                    }
                }
                
                if self.config.debug_mode:
                    logger.info(f"Ollama连接成功，发现 {len(models)} 个模型")
                
                return result
            else:
                error_msg = f'HTTP {response.status_code}: {response.text}'
                logger.error(f"Ollama连接失败: {error_msg}")
                return {
                    'status': 'error',
                    'base_url': self.base_url,
                    'error': error_msg,
                    'connection_test': 'failed'
                }
                
        except requests.exceptions.ConnectionError as e:
            error_msg = 'Cannot connect to Ollama service. Please check if Docker container is running.'
            logger.error(f"Ollama连接错误: {e}")
            return {
                'status': 'disconnected',
                'base_url': self.base_url,
                'error': error_msg,
                'connection_test': 'failed',
                'troubleshooting': [
                    'Check if Docker is running: docker ps',
                    'Check if Ollama container is running: docker-compose ps',
                    'Start Ollama service: docker-compose up -d ollama',
                    'Check container logs: docker-compose logs ollama'
                ]
            }
        except requests.exceptions.Timeout as e:
            error_msg = 'Connection timeout. Ollama service might be starting up.'
            logger.warning(f"Ollama连接超时: {e}")
            return {
                'status': 'timeout',
                'base_url': self.base_url,
                'error': error_msg,
                'connection_test': 'failed'
            }
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            logger.error(f"Ollama连接异常: {e}")
            return {
                'status': 'error',
                'base_url': self.base_url,
                'error': error_msg,
                'connection_test': 'failed'
            }
    
    def list_models(self) -> Dict[str, Any]:
        """
        获取可用的模型列表
        
        Returns:
            dict: 模型列表信息
        """
        try:
            response = self._make_request_with_retry(
                method='GET',
                url=f"{self.base_url}/api/tags"
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                model_details = []
                for model in models:
                    model_info = {
                        'name': model.get('name', ''),
                        'size': model.get('size', 0),
                        'digest': model.get('digest', ''),
                        'modified_at': model.get('modified_at', ''),
                        'details': model.get('details', {}),
                        'is_default_chat': model.get('name', '') == self.config.default_chat_model,
                        'is_default_code_review': model.get('name', '') == self.config.default_code_review_model,
                        'is_default_commit_analysis': model.get('name', '') == self.config.default_commit_analysis_model,
                    }
                    model_details.append(model_info)
                
                result = {
                    'status': 'success',
                    'models': model_details,
                    'models_count': len(model_details),
                    'default_models': {
                        'chat': self.config.default_chat_model,
                        'code_review': self.config.default_code_review_model,
                        'commit_analysis': self.config.default_commit_analysis_model
                    }
                }
                
                if self.config.debug_mode:
                    logger.info(f"获取到 {len(model_details)} 个模型")
                
                return result
            else:
                error_msg = f'Failed to fetch models: HTTP {response.status_code}'
                logger.error(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg,
                    'message': response.text
                }
                
        except Exception as e:
            error_msg = f'Failed to list models: {str(e)}'
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg
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
            
            logger.info(f"开始拉取模型: {model_name}")
            
            response = self._make_request_with_retry(
                method='POST',
                url=f"{self.base_url}/api/pull",
                json=payload,
                timeout=self.model_pull_timeout
            )
            
            if response.status_code == 200:
                logger.info(f"模型拉取成功: {model_name}")
                return {
                    'status': 'success',
                    'message': f'Model {model_name} pulled successfully',
                    'model_name': model_name
                }
            else:
                error_msg = f'Failed to pull model: HTTP {response.status_code}'
                logger.error(f"模型拉取失败: {model_name} - {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'message': response.text,
                    'model_name': model_name
                }
                
        except requests.exceptions.Timeout as e:
            error_msg = 'Model pull timeout. The operation might still be running in background.'
            logger.warning(f"模型拉取超时: {model_name}")
            return {
                'status': 'timeout',
                'error': error_msg,
                'model_name': model_name
            }
        except Exception as e:
            error_msg = f'Failed to pull model: {str(e)}'
            logger.error(f"模型拉取异常: {model_name} - {e}")
            return {
                'status': 'error',
                'error': error_msg,
                'model_name': model_name
            }
    
    def _validate_content_length(self, content: str, content_type: str = 'general') -> bool:
        """
        验证内容长度
        
        Args:
            content: 内容
            content_type: 内容类型
            
        Returns:
            bool: 是否通过验证
        """
        max_length = self.config.max_prompt_length
        
        if content_type == 'code':
            max_length = self.config.max_code_length
        
        if len(content) > max_length:
            logger.warning(f"内容长度 ({len(content)}) 超过限制 ({max_length})")
            return False
        
        return True
    
    def _get_prompt_template(self, repo_owner: str = None, repo_name: str = None, template_type: str = 'code_review') -> str:
        """
        获取提示词模板，优先使用仓库配置的自定义模板，否则使用默认模板
        
        Args:
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            template_type: 模板类型 ('code_review' 或 'commit_analysis')
            
        Returns:
            str: 提示词模板
        """
        # 如果提供了仓库信息，尝试获取自定义模板
        if repo_owner and repo_name:
            try:
                from .models import RepositoryConfig
                
                repo_config = RepositoryConfig.objects.filter(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    is_enabled=True
                ).first()
                
                if repo_config and repo_config.ollama_prompt_template:
                    logger.info(f"使用仓库 {repo_owner}/{repo_name} 的自定义提示词模板")
                    # 返回自定义模板，标记为自定义类型
                    return {"template": repo_config.ollama_prompt_template, "is_custom": True}
                    
            except Exception as e:
                logger.warning(f"获取仓库配置失败，使用默认模板: {e}")
        
        # 返回默认模板，标记为默认类型
        if template_type == 'code_review':
            return {"template": self._get_default_code_review_template(), "is_custom": False}
        elif template_type == 'commit_analysis':
            return {"template": self._get_default_commit_analysis_template(), "is_custom": False}
        else:
            return {"template": self._get_default_code_review_template(), "is_custom": False}
    
    def _get_default_code_review_template(self) -> str:
        """获取默认的代码审查提示词模板"""
        return """You are a senior code reviewer ensuring high standards of code quality and security.
Here is the submitted code：{code_content}
When invoked:

1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:

- Code is simple and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:

- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.

Finally answer me in Chinese"""
    
    def _get_default_commit_analysis_template(self) -> str:
        """获取默认的提交分析提示词模板"""
        return """You are a senior code reviewer ensuring high standards of code quality and security.
commit_message: {commit_message}{author_info}
code_diff:
```diff
{code_diff}
```

When invoked:

1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:

- Code is simple and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:

- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
Finally answer me in Chinese"""
    
    def chat(self, model_name: str = None, messages: List[Dict[str, str]] = None, stream: bool = None) -> Dict[str, Any]:
        """
        与模型进行对话
        
        Args:
            model_name: 模型名称，默认使用配置中的默认聊天模型
            messages: 对话消息列表，格式: [{"role": "user", "content": "Hello"}]
            stream: 是否使用流式响应，默认使用配置中的设置
            
        Returns:
            dict: 对话结果
        """
        # 使用默认值
        model_name = model_name or self.config.default_chat_model
        messages = messages or []
        stream = stream if stream is not None else self.config.enable_streaming
        
        # 验证消息内容长度
        total_content = ' '.join([msg.get('content', '') for msg in messages])
        if not self._validate_content_length(total_content):
            return {
                'status': 'error',
                'error': f'Content too long. Maximum length: {self.config.max_prompt_length}',
                'model': model_name
            }
        
        try:
            payload = {
                'model': model_name,
                'messages': messages,
                'stream': stream
            }
            
            if self.config.debug_mode:
                logger.info(f"开始对话，模型: {model_name}, 消息数: {len(messages)}")
            
            response = self._make_request_with_retry(
                method='POST',
                url=f"{self.base_url}/api/chat",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    'status': 'success',
                    'response': data.get('message', {}).get('content', ''),
                    'model': data.get('model', model_name),
                    'created_at': data.get('created_at', ''),
                    'done': data.get('done', True),
                    'total_duration': data.get('total_duration', 0),
                    'load_duration': data.get('load_duration', 0),
                    'prompt_eval_count': data.get('prompt_eval_count', 0),
                    'eval_count': data.get('eval_count', 0),
                    'config_used': {
                        'model': model_name,
                        'stream': stream,
                        'max_retries': self.max_retries
                    }
                }
                
                if self.config.debug_mode:
                    logger.info(f"对话完成，响应长度: {len(result['response'])}")
                
                return result
            else:
                error_msg = f'Chat request failed: HTTP {response.status_code}'
                logger.error(f"对话请求失败: {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'message': response.text,
                    'model': model_name
                }
                
        except Exception as e:
            error_msg = f'Chat request failed: {str(e)}'
            logger.error(f"对话请求异常: {e}")
            return {
                'status': 'error',
                'error': error_msg,
                'model': model_name
            }
    
    def generate(self, model_name: str = None, prompt: str = '', stream: bool = None) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            model_name: 模型名称，默认使用配置中的默认聊天模型
            prompt: 输入提示
            stream: 是否使用流式响应，默认使用配置中的设置
            
        Returns:
            dict: 生成结果
        """
        # 使用默认值
        model_name = model_name or self.config.default_chat_model
        stream = stream if stream is not None else self.config.enable_streaming
        
        # 验证提示长度
        if not self._validate_content_length(prompt):
            return {
                'status': 'error',
                'error': f'Prompt too long. Maximum length: {self.config.max_prompt_length}',
                'model': model_name
            }
        
        try:
            payload = {
                'model': model_name,
                'prompt': prompt,
                'stream': stream
            }
            
            if self.config.debug_mode:
                logger.info(f"开始生成文本，模型: {model_name}, 提示长度: {len(prompt)}")
            
            response = self._make_request_with_retry(
                method='POST',
                url=f"{self.base_url}/api/generate",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    'status': 'success',
                    'response': data.get('response', ''),
                    'model': data.get('model', model_name),
                    'created_at': data.get('created_at', ''),
                    'done': data.get('done', True),
                    'context': data.get('context', []),
                    'total_duration': data.get('total_duration', 0),
                    'load_duration': data.get('load_duration', 0),
                    'prompt_eval_count': data.get('prompt_eval_count', 0),
                    'eval_count': data.get('eval_count', 0),
                    'config_used': {
                        'model': model_name,
                        'stream': stream,
                        'max_retries': self.max_retries
                    }
                }
                
                if self.config.debug_mode:
                    logger.info(f"文本生成完成，响应长度: {len(result['response'])}")
                
                return result
            else:
                error_msg = f'Generate request failed: HTTP {response.status_code}'
                logger.error(f"生成请求失败: {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'message': response.text,
                    'model': model_name
                }
                
        except Exception as e:
            error_msg = f'Generate request failed: {str(e)}'
            logger.error(f"生成请求异常: {e}")
            return {
                'status': 'error',
                'error': error_msg,
                'model': model_name
            }
    
    def code_review(self, code_content: str, model_name: str = None, repo_owner: str = None, repo_name: str = None) -> Dict[str, Any]:
        """
        代码审查功能
        
        Args:
            code_content: 要审查的代码内容
            model_name: 使用的模型名称，默认使用配置中的代码审查模型
            repo_owner: 仓库所有者（用于获取自定义提示词）
            repo_name: 仓库名称（用于获取自定义提示词）
            
        Returns:
            dict: 代码审查结果
        """
        model_name = model_name or self.config.default_code_review_model
        
        # 验证代码长度
        if not self._validate_content_length(code_content, 'code'):
            return {
                'status': 'error',
                'error': f'Code too long. Maximum length: {self.config.max_code_length}',
                'model': model_name
            }
        
        # 获取提示词模板
        template_info = self._get_prompt_template(repo_owner, repo_name, 'code_review')
        
        # 根据模板类型处理提示词
        if template_info["is_custom"]:
            # 自定义模板：直接拼接代码内容
            prompt = f"{template_info['template']}\n\n以下是需要审查的代码：\n```\n{code_content}\n```"
            logger.info("使用自定义提示词模板，采用拼接方式")
        else:
            # 默认模板：使用占位符替换
            prompt = template_info["template"].format(code_content=code_content)
            logger.info("使用默认提示词模板，采用占位符替换")
        
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
        
        if self.config.debug_mode:
            logger.info(f"开始代码审查，代码长度: {len(code_content)}, 模型: {model_name}")
        
        result = self.chat(model_name, messages)
        
        if result['status'] == 'success':
            result['review_type'] = 'code_review'
            result['code_length'] = len(code_content)
            result['model_used'] = model_name
            result['config_limits'] = {
                'max_code_length': self.config.max_code_length,
                'max_prompt_length': self.config.max_prompt_length
            }
            
            if self.config.debug_mode:
                logger.info(f"代码审查完成，审查意见长度: {len(result.get('response', ''))}")
        
        return result
    
    def explain_commit(self, commit_message: str, code_diff: str, author_name: str = None, model_name: str = None, repo_owner: str = None, repo_name: str = None) -> Dict[str, Any]:
        """
        解释提交内容 - 简化版本，直接接受参数
        
        Args:
            commit_message: 提交消息
            code_diff: 代码差异
            author_name: 提交作者（可选）
            model_name: 使用的模型名称，默认使用配置中的提交分析模型
            repo_owner: 仓库所有者（用于获取自定义提示词）
            repo_name: 仓库名称（用于获取自定义提示词）
            
        Returns:
            dict: 提交解释结果
        """
        model_name = model_name or self.config.default_commit_analysis_model
        
        # 限制代码差异长度
        if len(code_diff) > self.config.max_code_length:
            logger.warning(f"代码差异长度 ({len(code_diff)}) 超过限制 ({self.config.max_code_length})")
            code_diff = code_diff[:self.config.max_code_length] + "\n...[内容被截断]"
        
        # 构造作者信息
        author_info = f"\n作者: {author_name}" if author_name else ""
        
        # 获取提示词模板
        template_info = self._get_prompt_template(repo_owner, repo_name, 'commit_analysis')
        
        # 根据模板类型处理提示词
        if template_info["is_custom"]:
            # 自定义模板：直接拼接提交信息和代码差异
            prompt = f"{template_info['template']}\n\n"
            prompt += f"提交信息: {commit_message}{author_info}\n\n"
            prompt += f"代码变更:\n```diff\n{code_diff}\n```"
            logger.info("使用自定义提示词模板，采用拼接方式")
        else:
            # 默认模板：使用占位符替换
            prompt = template_info["template"].format(
                commit_message=commit_message,
                author_info=author_info,
                code_diff=code_diff
            )
            logger.info("使用默认提示词模板，采用占位符替换")
        
        # 验证总内容长度
        if not self._validate_content_length(prompt):
            return {
                'status': 'error',
                'error': f'Commit data too long. Maximum length: {self.config.max_prompt_length}',
                'model': model_name
            }
        
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
        
        if self.config.debug_mode:
            logger.info(f"开始提交分析，代码长度: {len(code_diff)}, 模型: {model_name}")
        
        result = self.chat(model_name, messages)
        
        if result['status'] == 'success':
            result['analysis_type'] = 'commit_explanation'
            result['commit_sha'] = ''  # 不再需要，调用方会处理
            result['model_used'] = model_name
            result['config_limits'] = {
                'max_prompt_length': self.config.max_prompt_length,
                'max_code_length': self.config.max_code_length
            }
            
            if self.config.debug_mode:
                logger.info(f"提交分析完成，分析结果长度: {len(result.get('response', ''))}")
        
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
                'connection_timeout': self.connection_timeout,
                'request_timeout': self.request_timeout,
                'max_retries': self.max_retries,
                'retry_delay': self.retry_delay,
                'available_models': connection_status.get('available_models', []),
                'models_count': models_info.get('models_count', 0),
                'config_loaded': True
            },
            'connection_details': connection_status,
            'models_details': models_info.get('models', []),
            'configuration': ollama_config.to_dict(),
            'capabilities': [
                'code_review',
                'commit_explanation', 
                'text_generation',
                'chat_conversation',
                'model_management',
                'retry_mechanism',
                'content_validation',
                'logging_support'
            ]
        }


# 创建全局实例
ollama_client = OllamaClient()
