"""
Webhook服务层
封装webhook处理后的业务逻辑，包括POST成功后触发GET请求等操作
"""

import json
from django.http import JsonResponse
from .git_client import GitHubWebhookClient, GitHubDataClient


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
                # GET请求失败不影响原POST响应，但记录错误信息
                try:
                    response_data = json.loads(response.content.decode('utf-8'))
                except:
                    response_data = {'status': 'success', 'message': 'POST processed successfully'}
                
                response_data['triggered_get_request'] = {
                    'status': 'error',
                    'message': f'GET请求触发失败: {str(e)}',
                    'event_type': event_type
                }
                return JsonResponse(response_data, status=200)
        else:
            # POST请求失败，直接返回原响应
            return response
    
    def _trigger_recent_commits_get(self):
        """触发获取最近提交的GET请求"""
        return self.data_client.get_data('recent_commits', branch='main', limit=5)
    
    def _trigger_webhook_status_get(self):
        """触发webhook状态检查的GET请求"""
        webhook_stats = self.github_client.get_webhook_stats()
        return {
            'status': 'success',
            'webhook_configuration': webhook_stats
        }
    
    def _trigger_client_status_get(self):
        """触发客户端状态检查的GET请求"""
        return self.data_client.get_data('client_status')


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
    service = WebhookService()
    return service.process_webhook_with_get_trigger(request, event_type, payload)
