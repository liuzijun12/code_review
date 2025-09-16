"""
配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, List, Dict

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 尝试多个位置加载 .env 文件
def load_environment():
    """加载环境变量文件"""
    env_paths = [
        BASE_DIR / '.env',           # 当前目录
        BASE_DIR.parent / '.env',    # 上级目录  
        BASE_DIR / 'example.env',    # 示例文件
        BASE_DIR.parent / 'example.env'
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"加载配置文件: {env_path.name}")
            return True
    
    print("未找到配置文件，使用默认配置")
    return False

# 加载环境变量
load_environment()

class Config:
    """配置类"""
    
    # GitHub配置
    GITHUB_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN', '')

    # 仓库配置
    REPO_OWNER = os.getenv('REPO_OWNER', '')
    REPO_NAME = os.getenv('REPO_NAME', '')
    
    # OpenAI配置
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    
    # Ollama配置
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    
    # 模型配置
    FAST_MODEL = os.getenv('FAST_MODEL', 'qwen2.5-coder:7b')  # 快速响应
    QUALITY_MODEL = os.getenv('QUALITY_MODEL', 'qwen2.5-coder:32b')  # 高质量
    
    # 企业微信配置
    WECHAT_WEBHOOK_URL = os.getenv('WECHAT_WEBHOOK_URL', '')
    
    # 监控配置
    MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '300'))  # 5分钟检查一次
    BATCH_PROCESS_TIME = os.getenv('BATCH_PROCESS_TIME', '02:00')  # 夜间批处理时间
    
    # API配置
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))
    API_RETRY_COUNT = int(os.getenv('API_RETRY_COUNT', '3'))
    
    @classmethod
    def validate(cls):
        """验证必需的配置"""
        errors = []
        
        if not cls.GITHUB_TOKEN:
            errors.append("缺少 GITHUB_ACCESS_TOKEN")
        elif len(cls.GITHUB_TOKEN) < 20:
            errors.append("GITHUB_ACCESS_TOKEN 格式不正确")
            
        if not cls.REPO_OWNER:
            errors.append("缺少 REPO_OWNER")
            
        if not cls.REPO_NAME:
            errors.append("缺少 REPO_NAME")
        
        return errors
    
    @classmethod
    def get_masked_token(cls, token):
        """获取脱敏的token（用于日志）"""
        if not token:
            return "未配置"
        if len(token) < 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"
    
    @classmethod
    def print_config(cls):
        """打印配置信息（脱敏）"""
        print("\n📋 当前配置:")
        print(f"   GitHub Token: {cls.get_masked_token(cls.GITHUB_TOKEN)}")
        print(f"   仓库: {cls.REPO_OWNER}/{cls.REPO_NAME}")
        print(f"   OpenAI Key: {cls.get_masked_token(cls.OPENAI_API_KEY)}")
        print(f"   Ollama URL: {cls.OLLAMA_BASE_URL}")
        
        # 验证配置
        errors = cls.validate()
        if errors:
            print("\n⚠️  配置问题:")
            for error in errors:
                print(f"   {error}")
        else:
            print("✅ 配置验证通过")

def check_config():
    """检查配置是否正确"""
    return len(Config.validate()) == 0
    