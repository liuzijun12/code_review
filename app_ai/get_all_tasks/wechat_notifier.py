"""
WeChat Work (Enterprise WeChat) Notification Module

Send repository analysis results to WeChat Work group.
"""
import logging
import requests
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WeChatNotifier:
    """WeChat Work notification client"""
    
    def __init__(self, webhook_url: str):
        """
        Initialize WeChat notifier
        
        Args:
            webhook_url: WeChat Work webhook URL
        """
        self.webhook_url = webhook_url
        self.timeout = 10
    
    def send_text(self, content: str) -> Dict[str, Any]:
        """
        Send text message
        
        Args:
            content: Message content
        
        Returns:
            {'status': 'success'/'error', 'message': str}
        """
        payload = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        return self._send_request(payload)
    
    def send_markdown(self, content: str) -> Dict[str, Any]:
        """
        Send markdown message
        
        Args:
            content: Markdown content
        
        Returns:
            {'status': 'success'/'error', 'message': str}
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        return self._send_request(payload)
    
    def send_analysis_result(
        self,
        repository: str,
        file_count: int,
        summary: str,
        model: str,
        content_length: int,
        task_status: str = "success"
    ) -> Dict[str, Any]:
        """
        Send repository analysis result
        
        Args:
            repository: Repository name (owner/repo)
            file_count: Number of files analyzed
            summary: Analysis summary
            model: AI model used
            content_length: Total content length
            task_status: Task status ('success' or 'error')
        
        Returns:
            {'status': 'success'/'error', 'message': str}
        """
        # Build markdown message
        if task_status == "success":
            status_emoji = "✅"
            status_text = "Analysis Completed"
        else:
            status_emoji = "❌"
            status_text = "Analysis Failed"
        
        # Format timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build markdown content
        markdown_content = f"""# {status_emoji} **Repository Code Analysis Report**

---

**Repository:** `{repository}`
**Status:** <font color="info">{status_text}</font>
**Time:** {timestamp}

---

## 📊 **Analysis Statistics**

- **Files Analyzed:** {file_count} files
- **Content Size:** {content_length:,} characters
- **AI Model:** {model}

---

## 📝 **Analysis Summary**

{summary}

---

<font color="comment">Automated analysis by Code Review System</font>
"""
        
        return self.send_markdown(markdown_content)
    
    def _send_request(self, payload: Dict) -> Dict[str, Any]:
        """
        Send request to WeChat Work webhook
        
        Args:
            payload: Request payload
        
        Returns:
            {'status': 'success'/'error', 'message': str}
        """
        try:
            logger.info(f"Sending message to WeChat Work...")
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info("Message sent successfully")
                    return {
                        'status': 'success',
                        'message': 'Message sent successfully'
                    }
                else:
                    error_msg = result.get('errmsg', 'Unknown error')
                    logger.error(f"WeChat API error: {error_msg}")
                    return {
                        'status': 'error',
                        'message': f"WeChat API error: {error_msg}"
                    }
            else:
                logger.error(f"HTTP error: {response.status_code}")
                return {
                    'status': 'error',
                    'message': f"HTTP {response.status_code}"
                }
        
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {
                'status': 'error',
                'message': 'Request timeout'
            }
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }


def get_wechat_webhook_from_db(repo_owner: str, repo_name: str) -> Optional[str]:
    """
    Get WeChat webhook URL from database
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
    
    Returns:
        Webhook URL or None
    """
    try:
        from app_ai.models import RepositoryConfig
        
        repo_config = RepositoryConfig.objects.filter(
            repo_owner=repo_owner,
            repo_name=repo_name,
            is_enabled=True
        ).first()
        
        if repo_config and repo_config.wechat_webhook_url:
            logger.info(f"Found WeChat webhook for {repo_owner}/{repo_name}")
            return repo_config.wechat_webhook_url
        else:
            logger.warning(f"No WeChat webhook configured for {repo_owner}/{repo_name}")
            return None
    
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        return None


def send_analysis_to_wechat(
    repo_owner: str,
    repo_name: str,
    analysis_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send analysis result to WeChat Work
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        analysis_result: Analysis result dict
    
    Returns:
        {'status': 'success'/'error', 'message': str}
    """
    try:
        # Get webhook URL from database
        webhook_url = get_wechat_webhook_from_db(repo_owner, repo_name)
        
        if not webhook_url:
            return {
                'status': 'skipped',
                'message': 'No WeChat webhook configured'
            }
        
        # Create notifier
        notifier = WeChatNotifier(webhook_url)
        
        # Extract analysis info
        repository = analysis_result.get('repository', f"{repo_owner}/{repo_name}")
        file_count = analysis_result.get('file_count', 0)
        summary = analysis_result.get('summary', 'No summary available')
        model = analysis_result.get('model', 'Unknown')
        content_length = analysis_result.get('content_length', 0)
        task_status = analysis_result.get('status', 'unknown')
        
        # Send message
        result = notifier.send_analysis_result(
            repository=repository,
            file_count=file_count,
            summary=summary,
            model=model,
            content_length=content_length,
            task_status=task_status
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to send to WeChat: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


# ==================== Test Code ====================

if __name__ == '__main__':
    """
    Test Usage (Manual Testing Only)
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*80)
    print("WeChat Work Notifier - Test")
    print("="*80 + "\n")
    
    # Example webhook URL (replace with your own)
    test_webhook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
    
    print("Note: This is a manual test example.")
    print("To test, replace test_webhook with your actual WeChat webhook URL.\n")
    
    # Test 1: Send text message
    # notifier = WeChatNotifier(test_webhook)
    # result = notifier.send_text("Hello from Code Review System!")
    # print(f"Text message result: {result}")
    
    # Test 2: Send analysis result
    # analysis_result = {
    #     'repository': 'test/repo',
    #     'file_count': 10,
    #     'summary': 'This is a test summary.',
    #     'model': 'llama3.1:8B',
    #     'content_length': 5000,
    #     'status': 'success'
    # }
    # result = notifier.send_analysis_result(**analysis_result)
    # print(f"Analysis result: {result}")
    
    print("Test completed.\n")

