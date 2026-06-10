"""
精简日报生成+推送
格式：编号 | 严重度 | 概要 | 状态
"""
import json, os, requests
from collections import Counter
from datetime import datetime

DATA_DIR = "/root/jira_agent/data"
FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"

CONTROLLER_VALUE = "ICC-视觉"
TARGET_STATUSES = {"已分配", "分析中", "修复中"}
PRIO_EMOJI = {"Highest": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}


def parse_cf(val):
    if val is None:
        return ""
    if isinstance(val, dict):
        return val.get("value", val.get("name", str(val)))
    if isinstance(val, list):
        return ", ".join(
            v.get("value", v.get("name", str(v))) if isinstance(v, dict) else str(v)
            for v in val
        )
    return str(val)


def get_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10,
    )
    return resp.json().get("tenant_access_token", "")


def send(text):
    token = get_token()
    return requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": FEISHU_CHAT_ID, "msg_type": "text",
              "content": json.dumps({"text": text})},
        timeout=15,
    ).json()


def build_report():
    files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.startswith("jira_") and f.endswith(".json")],
        reverse=True,
    )
    if not files:
        return None
    with open(os.path.join(DATA_DIR, files[0])) as f:
        data = json.load(f)

    issues = data.get("issues", [])
    active = []
    for i in issues:
        cf = parse_cf(i.get("fields", {}).get("customfield_10500", ""))
        if CONTROLLER_VALUE not in cf:
            continue
        status = i.get("fields", {}).get("status", {}).get("name", "")
        if status not in TARGET_STATUSES:
            continue
        active.append(i)

    if not active:
        return f"📊 E0V Jira 待处理日报\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n✅ 暂无待处理 Case 🎉"

    visual = [i for i in active if "健康检测" not in i.get("fields", {}).get("summary", "")]
    health = [i for i in active if "健康检测" in i.get("fields", {}).get("summary", "")]

    sevs = Counter(
        (i.get("fields", {}).get("priority") or {}).get("name", "-") for i in active
    )

    prio_line = "  ".join(
        f"{PRIO_EMOJI.get(k, '⚪')}{k}:{c}" for k, c in sevs.most_common()
    )

    lines = [
        f"📊 E0V Jira 待处理日报",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"控制器: ICC-视觉 | 待处理: {len(active)} 条",
        f"优先级: {prio_line}",
        f"",
    ]

    for cat, emoji, cases in [("视觉", "👁️", visual), ("健康检测", "💊", health)]:
        if not cases:
            continue
        lines.append(f"{emoji} {cat}（{len(cases)}条）")
        for idx, i in enumerate(cases, 1):
            k = i["key"]
            fld = i.get("fields", {})
            s = fld.get("summary", "?")
            st = fld.get("status", {}).get("name", "?")
            p = (fld.get("priority") or {}).get("name", "-")
            lines.append(
                f"{idx}. [{k}](https://yfjira.mychery.com/browse/{k}) / {st} / {p}"
            )
            lines.append(f"   {s[:80]}")
        lines.append("")

    lines.append("---")
    lines.append("🤖 全自动采集 · 服务器直连")

    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    if report:
        print(report)
        print("\n📤 推送飞书...")
        resp = send(report)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    else:
        print("❌ 无数据")
