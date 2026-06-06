"""
ICC-视觉 验收中 周报 — 服务端发送脚本
用法: python3 send_icc_weekly.py
     python3 send_icc_weekly.py --dry-run   # 只打印不推送
"""
import json, os, sys
from datetime import datetime
import requests

ICC_WEEKLY_DIR = "/root/jira_agent/data/icc_weekly"

# 飞书配置
FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"

os.makedirs(ICC_WEEKLY_DIR, exist_ok=True)


def load_latest_icc():
    """加载最新的 ICC 周报数据"""
    files = sorted(
        [f for f in os.listdir(ICC_WEEKLY_DIR) if f.endswith(".json")],
        reverse=True,
    )
    if not files:
        return None
    with open(os.path.join(ICC_WEEKLY_DIR, files[0])) as f:
        return json.load(f)


def format_icc_report(data):
    """格式化 ICC 周报"""
    issues = data.get("issues", [])
    ws = data.get("week_start", "?")
    we = data.get("week_end", "?")

    if not issues:
        return (
            f"📊 ICC-视觉 验收中 周报\n"
            f"📅 {ws} ~ {we}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"✅ 本周期无验收中的问题 🎉"
        )

    lines = [
        f"📊 ICC-视觉 验收中 周报",
        f"📅 {ws} ~ {we}",
        f"🔢 共 {len(issues)} 条",
        f"━━━━━━━━━━━━━━━━",
    ]

    for idx, issue in enumerate(issues, 1):
        fs = issue.get("fields", {})
        key = issue["key"]
        summary = fs.get("summary", "?")
        priority = fs.get("priority", {}).get("name", "-") if fs.get("priority") else "-"
        assignee = fs.get("assignee", {}).get("displayName", "未分配") if fs.get("assignee") else "未分配"
        updated = fs.get("updated", "?")[:10]
        desc = fs.get("description", "")
        if desc and len(desc) > 100:
            desc = desc[:100].replace("\n", " ") + "..."
        elif desc:
            desc = desc.replace("\n", " ")
        else:
            desc = ""

        lines.append(f"{idx}. [{key}] {summary}")
        lines.append(f"   优先级:{priority} | 经办人:{assignee} | 更新:{updated}")
        if desc:
            lines.append(f"   描述: {desc[:80]}")

    lines.append("━━━━━━━━━━━━━━━━")
    lines.append(f"🔗 https://yfjira.mychery.com/issues/?jql=project%3DE0V%20AND%20cf%5B10500%5D%20%3D%20%22ICC-%E8%A7%86%E8%A7%89%22%20AND%20status%20%3D%20%22%E9%AA%8C%E6%94%B6%E4%B8%AD%22")
    return "\n".join(lines)


def send_feishu(text):
    """推送到飞书群"""
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10,
    )
    token = resp.json().get("tenant_access_token", "")
    if not token:
        return {"error": f"获取token失败: {resp.text}"}

    resp2 = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "receive_id": FEISHU_CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
        timeout=15,
    )
    return resp2.json()


if __name__ == "__main__":
    data = load_latest_icc()
    if not data:
        print("❌ 无 ICC 周报数据")
        sys.exit(1)

    report = format_icc_report(data)
    print(report)

    if "--dry-run" in sys.argv:
        print("\n📝 干跑模式，不推送")
    else:
        print("\n📤 推送到飞书...")
        resp = send_feishu(report)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
