"""
Integrated Tasks Module

Celery task for repository code analysis.
"""
import logging
from typing import Dict, List, Optional, Any
from celery import shared_task

from .get_all_content import format_content_with_structure
from .ollama_all_setting import get_ollama_client, test_connection
from .wechat_notifier import send_analysis_to_wechat

logger = logging.getLogger(__name__)


@shared_task(name='app_ai.analyze_repository_summary')
def analyze_repository_summary_from_db(
    repo_owner: str,
    repo_name: str,
    file_types: Optional[List[str]] = None,
    max_size_kb: int = 100,
    ollama_url: Optional[str] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze repository from database config and generate summary
    
    Args:
        repo_owner: Repository owner (required)
        repo_name: Repository name (required)
        file_types: File types like ['.py', '.java']
        max_size_kb: Max file size (KB), default 100
        ollama_url: Ollama service URL (optional)
        model_name: Model name (optional)
    
    Returns:
        {
            'status': 'success'/'error',
            'repository': str,
            'summary': str,
            'file_count': int
        }
    
    Usage:
        # Async call
        task = analyze_repository_summary_from_db.delay('username', 'repo_name')
        result = task.get()
        
        # Sync call
        result = analyze_repository_summary_from_db('username', 'repo_name')
    """
    try:
        # Check Ollama connection
        ollama_status = test_connection()
        if ollama_status['status'] != 'connected':
            error = ollama_status.get('error', 'Connection failed')
            return {'status': 'error', 'error': f'Ollama: {error}'}
        
        # Get formatted content from database
        logger.info(f"Fetching repository from database: {repo_owner}/{repo_name}")
        content_str = format_content_with_structure(
            file_types=file_types,
            max_size_kb=max_size_kb,
            include_tree=True,
            separator="="*80,
            repo_owner=repo_owner,
            repo_name=repo_name,
            use_database=True
        )
        
        if content_str.startswith("Error:"):
            return {'status': 'error', 'error': content_str}
        
        # Extract repo info
        lines = content_str.split('\n')
        repository, file_count = None, 0
        for line in lines[:10]:
            if 'Repository:' in line:
                repository = line.split('Repository:')[1].strip()
            if 'Files:' in line:
                try:
                    file_count = int(line.split('Files:')[1].strip())
                except:
                    pass
        
        # Analyze with Ollama
        logger.info("Generating repository summary...")
        client = get_ollama_client(ollama_url, model_name)
        
        prompt = f"""
请分析这个代码仓库，并提供全面的分析报告：

{content_str}

请务必用中文回答，并涵盖以下内容：

You are a senior code reviewer ensuring high standards of code quality and security.

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

**重要：请全部使用中文回答，提供详细、专业的分析。**
"""
        
        result = client.generate(
            prompt,
            "你是一位资深的软件架构师和代码审查专家，擅长代码分析和质量评估。请用中文提供专业、详细的分析报告。"
        )
        
        if result['status'] == 'success':
            logger.info(f"Analysis completed for {repo_owner}/{repo_name}")
            analysis_result = {
                'status': 'success',
                'repository': repository or f"{repo_owner}/{repo_name}",
                'file_count': file_count,
                'summary': result['response'],
                'model': client.model_name,
                'content_length': len(content_str)
            }
            
            # Send to WeChat Work
            wechat_result = send_analysis_to_wechat(repo_owner, repo_name, analysis_result)
            logger.info(f"WeChat notification: {wechat_result['status']} - {wechat_result.get('message', 'N/A')}")
            analysis_result['wechat_notification'] = wechat_result
            
            return analysis_result
        else:
            error_result = {'status': 'error', 'error': result.get('error', 'Analysis failed')}
            
            # Send error to WeChat Work
            wechat_result = send_analysis_to_wechat(repo_owner, repo_name, error_result)
            logger.info(f"WeChat notification: {wechat_result['status']} - {wechat_result.get('message', 'N/A')}")
            error_result['wechat_notification'] = wechat_result
            
            return error_result
        
    except Exception as e:
        logger.error(f"Summary failed: {e}")
        import traceback
        traceback.print_exc()
        
        error_result = {'status': 'error', 'error': str(e)}
        
        # Send error to WeChat Work
        try:
            wechat_result = send_analysis_to_wechat(repo_owner, repo_name, error_result)
            logger.info(f"WeChat notification: {wechat_result['status']} - {wechat_result.get('message', 'N/A')}")
            error_result['wechat_notification'] = wechat_result
        except Exception as wechat_error:
            logger.error(f"WeChat notification failed: {wechat_error}")
        
        return error_result
