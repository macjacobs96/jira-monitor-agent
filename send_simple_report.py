"""
精简日报生成+推送
格式：编号 | 严重度 | 概要 | 状态
"""
import json, os, requests
from collections import Counter
from datetime import datetime

DATA_DIR = "/root/jira_agent/data"
# 群聊推送 Bot（Jira日报助手）
FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"

# 个人推送 Bot（OPENCLAW传输助手）
PERSONAL_APP_ID = "cli_aaab8dfe57391cb0"
PERSONAL_APP_SECRET = "KAYOuqXohBsnCEU2ahcF7cdqPWk2zE5E"
PERSONAL_OPEN_ID = "ou_6037630b2167f9c1dc08266965ae58df"

CONTROLLER_VALUE = "ICC-视觉"
ACTIVE_STATUSES = {"已分配", "分析中", "修复中", "验收中", "处理中", "挂起", "申请挂起中"}
CLOSED_STATUSES = {"完成", "已关闭", "已解决"}
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
        if status not in ACTIVE_STATUSES:
            continue
        active.append(i)

    # 健康检测 — 额外拉入全部控制器的活跃问题
    health_extra = []
    seen_keys = {i["key"] for i in active}
    for i in issues:
        if i["key"] in seen_keys:
            continue
        summary = i.get("fields", {}).get("summary", "")
        if "健康检测" not in summary:
            continue
        status = i.get("fields", {}).get("status", {}).get("name", "")
        if status in CLOSED_STATUSES:
            continue
        health_extra.append(i)

    active.extend(health_extra)

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
    w = __import__("datetime").datetime.now().weekday()
    footers = {
    0: "新的一周开始了，王晓宾（宾哥）提醒您看bug了",
    1: "你知道为什么宾哥和神父会羡慕日本吗？因为在日本，天上会掉小男孩",
    2: "你知道种族歧视的文言文怎么说吗？----以色列人",
    3: "今天周四，宾哥提醒你修完bug发版了。",
    4: "午时三刻，监斩官丢出令牌，刽子手举刀正要行刑。忽闻待斩王晓宾（宾哥）仰天大笑。刽子手愣了几秒，监斩官问：尔等为何发笑？片刻后，王晓宾（宾哥）答道：郎中果然没说错，每天笑一笑，可延长寿命三秒",
    5: "周六了，宾哥还在等你的bug",
    6: "周日，上帝都休息了，宾哥还在看Jira",
    }
    lines.append(footers.get(w))

    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    if report:
        print(report)

        # 群聊推送
        print("\n📤 推送飞书群...")
        resp = send(report)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
#
#        # 个人推送（用 OPENCLAW传输助手 bot）
#        p_token = requests.post(
#            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
#            json={"app_id": PERSONAL_APP_ID, "app_secret": PERSONAL_APP_SECRET},
#            timeout=10,
#        ).json().get("tenant_access_token", "")
#
#        resp2 = requests.post(
#            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
#            headers={"Authorization": f"Bearer {p_token}", "Content-Type": "application/json"},
#            json={"receive_id": PERSONAL_OPEN_ID, "msg_type": "text",
#                  "content": json.dumps({"text": report})},
#            timeout=15,
#        ).json()
#        print(f"📤 推送个人飞书: {'✅' if resp2.get('code') == 0 else '❌ ' + resp2.get('msg','')}")
#    else:
        print("❌ 无数据")
