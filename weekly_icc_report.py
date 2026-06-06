"""
ICC-视觉 验收中问题 周报
用法:
  python3 weekly_icc_report.py --diag     # 诊断：查看实际状态名、验证查询
  python3 weekly_icc_report.py            # 正式运行：拉取 → 格式化 → 推送飞书
  python3 weekly_icc_report.py --dry-run  # 仅拉取+打印，不推送

时间范围：上周六 00:00 ~ 本周五 23:59
查询条件：E0V项目 + 控制器=ICC-视觉 + 状态=验收中
"""
import requests, json, sys
from datetime import datetime, timedelta

# ── Jira 配置 ──
JIRA_URL = "https://yfjira.mychery.com"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
PROJECT_KEY = "E0V"
CONTROLLER_FIELD = "customfield_10500"
CONTROLLER_VALUE = "ICC-视觉"

# ── 飞书配置 ──
FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"

session = requests.Session()
session.auth = (JIRA_USER, JIRA_PASS)
session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})


def get_week_range():
    """计算 上周六 00:00 ~ 本周五 23:59"""
    today = datetime.now()
    # 本周一是哪天 (weekday: 0=Mon ... 6=Sun)
    weekday = today.weekday()
    # 上周六 = today - (weekday + 2) days
    last_saturday = today - timedelta(days=weekday + 2)
    last_saturday = last_saturday.replace(hour=0, minute=0, second=0, microsecond=0)
    # 本周五 = last_saturday + 6 days
    this_friday = last_saturday + timedelta(days=6)
    this_friday = this_friday.replace(hour=23, minute=59, second=59, microsecond=0)
    return last_saturday, this_friday


def jql_search(jql, label=""):
    """执行 JQL 快速查询"""
    try:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql, "maxResults": 1, "fields": "summary,status"},
            timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            issues = data.get("issues", [])
            sample = issues[0]["key"] if issues else "N/A"
            sample_status = issues[0]["fields"]["status"]["name"] if issues else "N/A"
            print(f"  {label}: {total} 条 (示例: {sample} [{sample_status}])")
            return total
        else:
            print(f"  {label}: HTTP {resp.status_code}")
            return 0
    except Exception as e:
        print(f"  {label}: 错误 {e}")
        return 0


def diag():
    """诊断模式：查看状态列表、验证查询条件"""
    print("🔍 ICC-视觉 验收中 周报 — 诊断")
    print()

    # 1. 时间范围
    start, end = get_week_range()
    print(f"📅 本周时间范围: {start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%Y-%m-%d %H:%M')}")
    print()

    # 2. 查所有可能的状态
    print("📋 E0V 项目所有 issue 状态:")
    jql_search(f"project={PROJECT_KEY}", "全部 E0V")

    # 3. 尝试不同状态名
    status_candidates = ["验收中", "验收", "待验收", "Acceptance", "Accepting", "验证中", "Verified", "UAT"]
    print("\n📋 尝试不同状态名:")
    for s in status_candidates:
        jql_search(f'project={PROJECT_KEY} AND status="{s}"', f'status="{s}"')

    # 4. 试几个 issue 看看都有什么状态
    print("\n📋 最近 10 条 E0V issue 的状态:")
    resp = session.get(f"{JIRA_URL}/rest/api/2/search",
        params={"jql": f"project={PROJECT_KEY} ORDER BY updated DESC",
                "maxResults": 10, "fields": "status,summary,customfield_10500"},
        timeout=30)
    if resp.status_code == 200:
        for i in resp.json().get("issues", []):
            fs = i.get("fields", {})
            sname = fs.get("status", {}).get("name", "?")
            cf = fs.get(CONTROLLER_FIELD, "")
            if isinstance(cf, dict):
                cf = cf.get("value", cf.get("name", "?"))
            print(f"  {i['key']}: [{sname}] 控制器={cf}  {fs.get('summary','')[:40]}")

    # 5. 带控制器的试试 — 多种 JQL 写法
    print(f"\n📋 控制器=ICC-视觉 — 多种 JQL 试法:")
    cf_jqls = [
        f'"{CONTROLLER_FIELD}" = "{CONTROLLER_VALUE}"',
        f'"{CONTROLLER_FIELD}" in ("{CONTROLLER_VALUE}")',
        f'"{CONTROLLER_FIELD}" ~ "{CONTROLLER_VALUE}"',
        f'cf[10500] = "{CONTROLLER_VALUE}"',
        f'"{CONTROLLER_FIELD}" = {CONTROLLER_VALUE}',
    ]
    for cf_jql in cf_jqls:
        jql = f'project={PROJECT_KEY} AND {cf_jql}'
        try:
            resp2 = session.get(f"{JIRA_URL}/rest/api/2/search",
                params={"jql": jql, "maxResults": 1, "fields": "status,summary"},
                timeout=15)
            code = resp2.status_code
            if code == 200:
                total = resp2.json().get("total", 0)
                print(f"  ✅ {cf_jql[:60]} → {total} 条")
            else:
                print(f"  ❌ {cf_jql[:60]} → HTTP {code}")
        except Exception as e:
            print(f"  ❌ {cf_jql[:60]} → {e}")


def fetch_issues(start_date, end_date, status_name="验收中"):
    """拉取符合条件的所有 issue"""
    date_fmt = "%Y-%m-%d"
    jql = (
        f'project={PROJECT_KEY}'
        f' AND cf[10500] = "{CONTROLLER_VALUE}"'
        f' AND status = "{status_name}"'
        f' AND updated >= "{start_date.strftime(date_fmt)}"'
        f' AND updated <= "{end_date.strftime(date_fmt)}"'
    )
    print(f"🔍 JQL: {jql}")

    fields = ("summary,status,priority,assignee,reporter,created,updated,"
              "resolutiondate,issuetype,labels,components,fixVersions,"
              "customfield_10500,description")

    all_issues = []
    start_at = 0
    max_results = 100

    while True:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql, "startAt": start_at,
                    "maxResults": max_results, "fields": fields},
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("total", 0)
        print(f"  已拉取 {len(all_issues)} / {total} 条...")
        if start_at + max_results >= total or total == 0:
            break
        start_at += max_results

    print(f"✅ 共拉取 {len(all_issues)} 条")
    return all_issues


def format_report(issues, start_date, end_date):
    """生成周报文本"""
    if not issues:
        return (
            f"📊 ICC-视觉 验收中 周报\n"
            f"📅 {start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"✅ 本周期无验收中的问题 🎉"
        )

    lines = [
        f"📊 ICC-视觉 验收中 周报",
        f"📅 {start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')}",
        f"🔢 共 {len(issues)} 条",
        f"━━━━━━━━━━━━━━━━",
    ]

    for idx, issue in enumerate(issues, 1):
        fs = issue.get("fields", {})
        key = issue["key"]
        summary = fs.get("summary", "?")
        status = fs.get("status", {}).get("name", "?")
        priority = fs.get("priority", {}).get("name", "?") if fs.get("priority") else "-"
        assignee = fs.get("assignee", {}).get("displayName", "未分配") if fs.get("assignee") else "未分配"
        updated = fs.get("updated", "?")[:10]
        desc = fs.get("description", "")
        # 截取 description 前100字符
        if desc and len(desc) > 100:
            desc_short = desc[:100].replace("\n", " ") + "..."
        elif desc:
            desc_short = desc.replace("\n", " ")
        else:
            desc_short = "无描述"

        lines.append(f"{idx}. [{key}] {summary}")
        lines.append(f"   优先级:{priority} | 经办人:{assignee} | 更新:{updated}")
        if desc_short != "无描述":
            lines.append(f"   描述: {desc_short[:80]}")

    lines.append("━━━━━━━━━━━━━━━━")
    link = f"https://yfjira.mychery.com/issues/?jql=project%3D{PROJECT_KEY}%20AND%20cf%5B10500%5D%20%3D%20%22ICC-%E8%A7%86%E8%A7%89%22%20AND%20status%20%3D%20%22%E9%AA%8C%E6%94%B6%E4%B8%AD%22"
    lines.append(f"🔗 Jira 链接: {link}")
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
        print(f"❌ 获取飞书 token 失败: {resp.text}")
        return None

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


def push_to_server(issues, start_date, end_date):
    """推送原始数据到服务器"""
    SERVER_URL = "http://43.159.43.36/api/jira/icc-weekly"
    payload = {
        "project": PROJECT_KEY,
        "fetched_at": datetime.now().isoformat(),
        "week_start": start_date.strftime("%Y-%m-%d"),
        "week_end": end_date.strftime("%Y-%m-%d"),
        "total": len(issues),
        "issues": issues,
    }
    resp = requests.post(SERVER_URL, json=payload, timeout=60)
    resp.raise_for_status()
    print(f"✅ 已推送 {len(issues)} 条到服务器: {resp.json()}")


# ════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--diag" in sys.argv:
        diag()
        sys.exit(0)

    start, end = get_week_range()
    print(f"📅 时间范围: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")

    # 可以从命令行传入实际状态名
    status_name = "验收中"
    for arg in sys.argv[1:]:
        if arg.startswith("--status="):
            status_name = arg.split("=", 1)[1]

    issues = fetch_issues(start, end, status_name)

    if "--push" in sys.argv:
        # 推送模式：只推数据到服务器
        push_to_server(issues, start, end)
    elif "--dry-run" in sys.argv:
        # 干跑：只打印
        report = format_report(issues, start, end)
        print("\n" + report)
        print("\n📝 干跑模式，不推送")
    else:
        # 独立模式：自己发飞书
        report = format_report(issues, start, end)
        print("\n" + report)
        if issues:
            print("\n📤 推送到飞书...")
            resp = send_feishu(report)
            print(json.dumps(resp, ensure_ascii=False, indent=2))
        else:
            print("\n📤 无数据，跳过推送")
