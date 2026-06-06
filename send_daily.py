"""
手动发送日报 / 定时任务入口
用法: python3 send_daily.py
"""
import sys
sys.path.insert(0, "/root/jira_agent")
from src.analyzer import load_latest, analyze, format_report
from server import send_feishu, get_feishu_token
import json

data = load_latest()
if not data:
    print("❌ 无数据，请先运行 jira_fetcher.py 同步")
    sys.exit(1)

result = analyze(data)
report = format_report(result)
print(report)
print("\n--- 发送到飞书 ---")
resp = send_feishu(report)
print(json.dumps(resp, ensure_ascii=False, indent=2))
