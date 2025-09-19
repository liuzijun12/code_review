"""
Webhook服务层
封装webhook处理后的业务逻辑，包括POST成功后触发GET请求等操作
"""

import json
import logging
from django.http import JsonResponse
from .git_client import GitHubWebhookClient, GitHubDataClient

# 创建logger实例
logger = logging.getLogger(__name__)


class WebhookService:
    """Webhook业务服务类"""
    
    def __init__(self):
        self.github_client = GitHubWebhookClient()
        self.data_client = GitHubDataClient()
    
    def process_webhook_with_get_trigger(self, request, event_type, payload):
        """
        处理webhook事件，并在POST成功后触发相应的GET请求
        
        Args:
            request: Django request对象
            event_type: GitHub事件类型
            payload: webhook payload
            
        Returns:
            JsonResponse: 包含原始响应和GET请求结果的响应
        """
        # 根据事件类型处理POST请求
        if event_type == 'push':
            response = self.github_client.handle_push_event(payload)
            get_trigger_func = self._trigger_recent_commits_get
            
        elif event_type == 'ping':
            response = self.github_client.handle_ping_event(payload)
            get_trigger_func = self._trigger_webhook_status_get
            
        else:
            logger.warning(f"不支持的事件类型: {event_type}")
            response = JsonResponse({
                'message': f'Event type "{event_type}" is not supported',
                'supported_events': ['push', 'ping'],
                'status': 'ignored'
            }, status=200)
            get_trigger_func = self._trigger_client_status_get
        
        # 检查POST响应状态码并触发GET请求
        return self._check_and_trigger_get(response, get_trigger_func, event_type)
    
    def _check_and_trigger_get(self, response, get_trigger_func, event_type):
        """
        检查POST响应状态码，如果是200则触发GET请求
        
        Args:
            response: POST请求的响应对象
            get_trigger_func: 要触发的GET请求函数
            event_type: 事件类型
            
        Returns:
            JsonResponse: 增强后的响应
        """
        if response.status_code == 200:
            try:
                # 解析原响应数据
                response_data = json.loads(response.content.decode('utf-8'))
                
                # 触发GET请求
                get_result = get_trigger_func()
                
                # 添加GET请求结果到响应中
                response_data['triggered_get_request'] = {
                    'status': 'success',
                    'message': f'{event_type}事件POST成功，GET请求已触发',
                    'event_type': event_type,
                    'get_data_result': get_result
                }
                
                # 如果GET请求成功，添加额外信息
                if get_result.get('status') == 'success':
                    response_data['triggered_get_request']['additional_info'] = '数据获取成功，可进行后续处理'
                
                return JsonResponse(response_data, status=200)
                
            except Exception as e:
                logger.error(f"GET请求触发失败: {str(e)}")
                
                # GET请求失败不影响原POST响应，但记录错误信息
                try:
                    response_data = json.loads(response.content.decode('utf-8'))
                except:
                    response_data = {'status': 'success', 'message': 'POST processed successfully'}
                
                response_data['triggered_get_request'] = {
                    'status': 'error',
                    'message': f'GET请求触发失败: {str(e)}',
                    'event_type': event_type,
                    'error_type': type(e).__name__
                }
                return JsonResponse(response_data, status=200)
        else:
            logger.warning(f"状态码非200 ({response.status_code})")
            # POST请求失败，直接返回原响应
            return response
    
    def _trigger_recent_commits_get(self):
        """触发获取最近提交的GET请求，快速保存到数据库，AI分析异步执行"""
        logger.info("触发recent_commits GET请求")
        
        # 获取recent_commits数据
        result = self.data_client.get_data('recent_commits', branch='main', limit=5)
        
        if result.get('status') == 'success':
            try:
                # 添加数据库保存逻辑
                if 'commits_data' in result and 'commits' in result['commits_data']:
                    commits = result['commits_data']['commits']
                    saved_count = 0
                    
                    logger.info(f"开始处理 {len(commits)} 个提交")
                    
                    for commit in commits:
                        try:
                            # 为每个提交获取详细信息（包含diff）
                            detail_result = self.data_client.get_data('commit_details', 
                                                                   sha=commit['sha'], 
                                                                   include_diff=True)
                            
                            if detail_result.get('status') == 'success':
                                # 使用详细信息构造GitHub数据格式
                                commit_detail = detail_result['commit_detail']['commit']
                                github_data = {
                                    'sha': commit_detail['sha'],
                                    'commit': {
                                        'author': {
                                            'name': commit_detail['author']['name'],
                                            'email': commit_detail['author']['email'],
                                            'date': commit_detail['timestamp']['authored_date']
                                        },
                                        'message': commit_detail['message']
                                    },
                                    'author': {
                                        'login': commit_detail['author']['username'],
                                        'avatar_url': commit_detail['author'].get('avatar_url')
                                    },
                                    'html_url': commit_detail['urls']['html_url'],
                                    'url': commit_detail['urls']['api_url'],
                                    'stats': commit_detail.get('stats', {}),
                                    'files': commit_detail.get('files', []),
                                    'parents': commit_detail.get('parents', []),
                                    'patch': commit_detail.get('raw_patch', '')
                                }
                                
                                # 保存到数据库
                                from .sql_client import DatabaseClient
                                success, message, _ = DatabaseClient.save_commit_to_database(github_data)
                                if success:
                                    saved_count += 1
                                    logger.info(f"保存提交: {commit['sha'][:8]}")
                                else:
                                    logger.warning(f"保存提交失败: {commit['sha'][:8]} - {message}")
                                
                            else:
                                # 如果获取详细信息失败，使用简化版本
                                logger.warning(f"获取提交详情失败，使用简化数据: {commit['sha'][:8]}")
                                github_data = {
                                    'sha': commit['sha'],
                                    'commit': {
                                        'author': {
                                            'name': commit['author'],
                                            'email': 'unknown@example.com',
                                            'date': commit['date']
                                        },
                                        'message': commit['message']
                                    },
                                    'author': {
                                        'login': 'unknown',
                                        'avatar_url': None
                                    },
                                    'html_url': commit['url'],
                                    'url': commit['url'],
                                    'stats': {},
                                    'files': [],
                                    'parents': [],
                                    'patch': ''
                                }
                                
                                # 保存基本数据（无AI分析）
                                from .sql_client import DatabaseClient
                                success, message, _ = DatabaseClient.save_commit_to_database(github_data)
                                if success:
                                    saved_count += 1
                                    logger.info(f"保存基本提交数据: {commit['sha'][:8]}")
                                else:
                                    logger.error(f"保存失败: {commit['sha'][:8]} - {message}")
                                
                        except Exception as commit_error:
                            logger.error(f"处理提交 {commit['sha'][:8]} 时出错: {commit_error}")
                            continue
                    
                    # 在结果中添加数据库保存状态
                    result['database_save'] = {
                        'success': True,
                        'message': f'Webhook触发：保存完成 {saved_count}/{len(commits)} 个提交',
                        'saved_count': saved_count,
                        'total_count': len(commits)
                    }
                    
                    logger.info(f"处理完成：保存 {saved_count}/{len(commits)} 个提交")
                    
            except Exception as e:
                logger.error(f"数据库保存过程出错: {e}")
                result['database_save'] = {
                    'success': False,
                    'message': f'Webhook触发：处理失败: {str(e)}',
                    'saved_count': 0
                }
        
        return result
    
    def _trigger_webhook_status_get(self):
        """触发webhook状态检查的GET请求"""
        webhook_stats = self.github_client.get_webhook_stats()
        return {
            'status': 'success',
            'webhook_configuration': webhook_stats
        }
    
    def _trigger_client_status_get(self):
        """触发客户端状态检查的GET请求"""
        result = self.data_client.get_data('client_status')
        return result


class WebhookResponseEnhancer:
    """Webhook响应增强器"""
    
    @staticmethod
    def enhance_response_with_metadata(response_data, event_type, execution_time=None):
        """
        为响应添加元数据信息
        
        Args:
            response_data: 响应数据字典
            event_type: 事件类型
            execution_time: 执行时间（可选）
            
        Returns:
            dict: 增强后的响应数据
        """
        if 'metadata' not in response_data:
            response_data['metadata'] = {}
        
        response_data['metadata'].update({
            'event_type': event_type,
            'processing_timestamp': json.loads(JsonResponse({}).content)['timestamp'] if hasattr(JsonResponse({}), 'content') else None,
            'has_triggered_get': 'triggered_get_request' in response_data,
            'execution_time_ms': execution_time
        })
        
        return response_data
    
    @staticmethod
    def add_processing_summary(response_data):
        """
        添加处理摘要信息
        
        Args:
            response_data: 响应数据字典
            
        Returns:
            dict: 包含摘要的响应数据
        """
        summary = {
            'post_success': response_data.get('status') == 'success',
            'get_triggered': 'triggered_get_request' in response_data,
            'get_success': response_data.get('triggered_get_request', {}).get('status') == 'success'
        }
        
        response_data['processing_summary'] = summary
        return response_data


# 便捷函数
def process_webhook_event(request, event_type, payload):
    """
    便捷函数：处理webhook事件并触发GET请求
    
    Args:
        request: Django request对象
        event_type: GitHub事件类型
        payload: webhook payload
        
    Returns:
        JsonResponse: 处理结果
    """
    logger.info(f"处理webhook事件: {event_type}")
    service = WebhookService()
    result = service.process_webhook_with_get_trigger(request, event_type, payload)
    return result
