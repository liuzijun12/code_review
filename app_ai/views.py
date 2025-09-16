from django.shortcuts import render
import git
import requests
import json
from ollama import Client
# Create your views here.
def get_new_commits():
    """获取未处理的新提交"""
    repo.remotes.origin.pull()  # 拉取最新代码
    # 对比本地记录与远程提交，返回新提交列表
    return new_commits


def analyze_commit(commit):
    """用模型分析单条提交"""
    # 提取提交信息
    diff = repo.git.diff(commit.parents[0], commit)
    prompt = f"分析以下代码变更并给出改进建议：\n{diff}"

    # 调用轻量模型快速分析
    response = ollama_client.chat(
        model="qwen2.5-coder:7b-instruct-q4_K_M",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]


def batch_summarize():
    """夜间批量汇总（调用32B模型）"""
    # 收集当日所有提交分析结果
    daily_analysis = collect_daily_analyses()

    prompt = f"汇总以下代码变更分析，给出整体改进建议：\n{daily_analysis}"
    response = ollama_client.chat(
        model="qwen2.5-coder:32b-instruct-q4_K_M",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]


def send_wechat_notification(content):
    """发送企业微信通知"""
    requests.post(
        WECHAT_WEBHOOK,
        json={"msgtype": "text", "text": {"content": content}}
    )
