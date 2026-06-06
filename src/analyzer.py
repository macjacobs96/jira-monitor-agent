"""
Jira Agent 服务端 —— 接收数据 / 分析 / 定时飞书推送
筛选条件: 控制器(单选)=ICC-视觉, 状态=已分配/分析中/修复中
"""
import json
import os
import random
from datetime import datetime, timedelta
from collections import Counter

DATA_DIR = "/root/jira_agent/data"
JIRA_BASE_URL = "https://yfjira.mychery.com/browse"
CONTROLLER_FIELD = "customfield_10500"
CONTROLLER_VALUE = "ICC-视觉"
TARGET_STATUSES = {"已分配", "分析中", "修复中"}

# 🎭 吉祥话库
QUIPS = [
    "🐶 关 Case 如遛狗，一天不溜就拆家。",
    "🦊 今天的 Bug 不会自己消失，但明天的你会更秃。",
    "🐱 修完这个 Bug，你就是全组最靓的仔。",
    "🦥 不着急，反正这个 Case 已经比你工龄长了。",
    "🐼 代码会骗你，但 Deadline 不会。",
    "🦉 发现问题的人是智者，解决问题的人是牛马。",
    "🐧 今天也是和 Bug 双向奔赴的一天呢～",
    "🦄 别慌，这个 Case 只是看起来难，实际上……确实很难。",
    "🐙 你的 Jira 就像章鱼烧，翻来覆去还是那几颗。",
    "🦖 别再 reopen 了，这个 Bug 快成项目组成员的共同记忆了。",
    "🐸 修完这个就去喝奶茶——然后发现还有 3 个。",
    "🦜 早安打工人，今天的 Bug 已为你备好。",
    "🐋 这个 Case 的寿命已经超过了我家的盆栽，respect。",
    "🦋 每一次 reopen 都是一次美丽的蜕变——骗你的，就是烦。",
    "🐿️ 少量 Bug 有益身心健康，你目前的状态是……过量。",
    "🦆 表面风平浪静，背后全是 Critical。",
    "🐝 你负责修 Bug，我负责阴阳你，我们都有光明的未来。",
    "🦩 加油！离下班还有……哦你加班啊，那没事了。",
    "🐃 今天的成就：成功识别了 3 个本来就该关的 Bug。",
    "🦚 这个 Case 的描述比我的命还长。",
    "🦔 你修的每一个 Bug 都在问：为什么要这样写代码？",
    "🐡 好消息：没有新增。坏消息：旧的也没少。",
    "🦢 优雅地打开 Jira → 优雅地崩溃 → 优雅地加班。",
    "🐴 建议把这个 Case 改名：我的青春。",
    "🦅 你不是在修 Bug，你是在为项目管理课准备素材。",
]

os.makedirs(DATA_DIR, exist_ok=True)


def load_latest():
    files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.endswith(".json")],
        reverse=True
    )
    if not files:
        return None
    with open(os.path.join(DATA_DIR, files[0])) as f:
        return json.load(f)


def save_snapshot(payload):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(DATA_DIR, f"jira_{ts}.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def parse_customfield(cf_value):
    """解析 Jira 自定义字段值（下拉/单选/多选）"""
    if cf_value is None:
        return ""
    if isinstance(cf_value, dict):
        return cf_value.get("value", cf_value.get("name", str(cf_value)))
    if isinstance(cf_value, list):
        return ", ".join(
            v.get("value", v.get("name", str(v))) if isinstance(v, dict) else str(v)
            for v in cf_value
        )
    return str(cf_value)


def filter_issues(issues):
    """按控制器 + 状态筛选"""
    filtered = []
    for i in issues:
        fields = i.get("fields", {})
        # 控制器过滤
        cf = parse_customfield(fields.get(CONTROLLER_FIELD, ""))
        if CONTROLLER_VALUE not in cf:
            continue
        # 状态过滤
        status = fields.get("status", {}).get("name", "")
        if status in TARGET_STATUSES:
            filtered.append(i)
    return filtered


def analyze(data):
    issues = data.get("issues", [])
    total_raw = len(issues)

    # 控制器筛选
    icc_issues = []
    for i in issues:
        cf = parse_customfield(i.get("fields", {}).get(CONTROLLER_FIELD, ""))
        if CONTROLLER_VALUE in cf:
            icc_issues.append(i)

    # 控制器 + 状态筛选
    active = filter_issues(icc_issues)

    if not active:
        return {
            "total": 0,
            "total_raw": total_raw,
            "icc_total": len(icc_issues),
            "message": "暂无待处理 Case 🎉",
            "cases": [],
            "overdue": [],
        }

    # 按类别分组：视觉 / 健康检测
    cases_by_status = {"视觉": [], "健康检测": []}
    for i in active:
        summary = i.get("fields", {}).get("summary", "")
        status = i.get("fields", {}).get("status", {}).get("name", "未知")
        key = i.get("key")
        category = "健康检测" if "健康检测" in summary else "视觉"
        cases_by_status[category].append({
            "key": key,
            "url": f"{JIRA_BASE_URL}/{key}",
            "status": status,
            "summary": i.get("fields", {}).get("summary", ""),
            "priority": (i.get("fields", {}).get("priority") or {}).get("name", "-"),
            "duedate": i.get("fields", {}).get("duedate"),
            "created": (i.get("fields", {}).get("created", "")[:10]),
        })

    # 逾期
    overdue = []
    now = datetime.now()
    for c in [c for cases in cases_by_status.values() for c in cases]:
        if c["duedate"]:
            try:
                due = datetime.strptime(c["duedate"], "%Y-%m-%d")
                if due < now:
                    overdue.append(c)
            except:
                pass

    # 优先级统计
    priority_count = Counter(c["priority"] for c in [c for cases in cases_by_status.values() for c in cases])

    return {
        "total": len(active),
        "total_raw": total_raw,
        "icc_total": len(icc_issues),
        "cases_by_status": cases_by_status,
        "cases": [c for cases in cases_by_status.values() for c in cases],
        "overdue": overdue,
        "overdue_count": len(overdue),
        "priority_count": dict(priority_count.most_common()),
    }


def format_report(analysis, project="E0V"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not analysis.get("cases"):
        return (
            f"📊 {project} Jira 待处理日报\n"
            f"🕐 {now}\n\n"
            f"控制器=ICC-视觉 共 {analysis.get('icc_total', 0)} 条 | "
            f"待处理 0 条 🎉"
        )

    status_order = [("视觉", "👁️"), ("健康检测", "💊")]
    cases_by_status = analysis["cases_by_status"]

    lines = [
        f"📊 {project} Jira 待处理日报",
        f"🕐 {now}",
        f"",
        f"控制器: {CONTROLLER_VALUE} | 待处理: **{analysis['total']}** 条",
    ]

    # 优先级概览
    if analysis.get("priority_count"):
        prio_line = []
        for p, c in analysis["priority_count"].items():
            emoji = {"Highest": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(p, "⚪")
            prio_line.append(f"{emoji}{p}:{c}")
        lines.append(f"优先级: {'  '.join(prio_line)}")

    # 逾期提醒
    if analysis.get("overdue_count", 0) > 0:
        lines.append(f"🚨 逾期: **{analysis['overdue_count']}** 条")
    lines.append("")

    # 按状态分组列出
    for cat, emoji in status_order:
        cases = cases_by_status.get(cat, [])
        if not cases:
            continue
        lines.append(f"## {emoji} {cat}（{len(cases)}）")
        lines.append("")
        for idx, c in enumerate(cases, 1):
            key = c['key']
            url = c['url']
            status = c.get("status", "-")
            prio = c.get("priority", "-")
            summary = c['summary']
            keyword = summary[:20] if summary else "-"
            lines.append(
                f"{idx}. [{key}]({url}) / {status} / {prio} / {keyword} / {summary}"
            )
        lines.append("")

    if analysis.get("overdue"):
        lines.append(f"## 🚨 逾期 Case（{analysis['overdue_count']}）")
        lines.append("")
        for c in analysis["overdue"][:10]:
            lines.append(f"[{c['key']}]({c['url']}) / 📅{c['duedate']} / {c['summary'][:50]}")
        lines.append("")

    # 吉祥话
    quip = random.choice(QUIPS)
    lines.append(f"---\n{quip}")

    return "\n".join(lines)


if __name__ == "__main__":
    data = load_latest()
    if data:
        result = analyze(data)
        print(format_report(result))
    else:
        print("暂无数据")
