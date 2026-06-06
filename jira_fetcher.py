"""
Jira 数据采集脚本 —— 智能诊断版
用法: python3 jira_fetcher.py           # 正常采集
      python3 jira_fetcher.py --diag     # 诊断模式
"""
import requests, json, sys
from datetime import datetime

JIRA_URL = "https://yfjira.mychery.com"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
PROJECT_KEY = "E0V"
ASSIGNEE = "商 汤API"
CONTROLLER_FIELD = "customfield_10500"
CONTROLLER_VALUE = "ICC-视觉"
SERVER_URL = "http://43.159.43.36/api/jira/sync"

session = requests.Session()
session.auth = (JIRA_USER, JIRA_PASS)
session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})


def jql_search(jql, label=""):
    """执行 JQL 并返回 total"""
    try:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql, "maxResults": 1, "fields": "summary"},
            timeout=30)
        if resp.status_code == 200:
            total = resp.json().get("total", 0)
            issues = resp.json().get("issues", [])
            sample = issues[0]["key"] if issues else "N/A"
            print(f"  {label}: {total} 条 (示例: {sample})")
            return total
        else:
            print(f"  {label}: HTTP {resp.status_code}")
            return 0
    except Exception as e:
        print(f"  {label}: 错误 {e}")
        return 0


def diag():
    print("🔍 Jira 诊断模式\n")

    # 1. 项目有没有 issue
    jql_search(f'project={PROJECT_KEY}', "项目=E0V")

    # 2. 经办人名称对不对
    jql_search(f'project={PROJECT_KEY} AND assignee=currentUser()', "当前用户")

    # 3. 试试不同的经办人写法
    for name in ["商汤API", "商汤", "ShangTang", "SenseAuto", "senseautoAPI"]:
        jql_search(f'project={PROJECT_KEY} AND assignee="{name}"', f'经办人="{name}"')

    # 4. 取一个 issue 看看 assignee 实际怎么写
    resp = session.get(f"{JIRA_URL}/rest/api/2/search",
        params={"jql": f"project={PROJECT_KEY}", "maxResults": 3,
                "fields": "assignee,summary"},
        timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n📋 最近 3 条 E0V issue 的经办人:")
        for i in data.get("issues", []):
            a = i["fields"].get("assignee")
            aname = a["displayName"] if a else "(未分配)"
            print(f"  {i['key']}: 经办人={aname}  {i['fields'].get('summary','')[:30]}")

    # 5. 看看控制器字段到底有没有值
    print(f"\n📋 带 {CONTROLLER_FIELD} 字段的 issue:")
    resp = session.get(f"{JIRA_URL}/rest/api/2/search",
        params={"jql": f"project={PROJECT_KEY} AND {CONTROLLER_FIELD} is not EMPTY",
                "maxResults": 3,
                "fields": f"summary,assignee,{CONTROLLER_FIELD}"},
        timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        print(f"  共 {data.get('total', 0)} 条")
        for i in data.get("issues", []):
            cf = i["fields"].get(CONTROLLER_FIELD, "?")
            if isinstance(cf, dict):
                cf = cf.get("value", cf.get("name", str(cf)))
            elif isinstance(cf, list):
                cf = [v.get("value", v.get("name", str(v))) if isinstance(v, dict) else v for v in cf]
            print(f"  {i['key']}: 控制器={cf}")
    else:
        print(f"  HTTP {resp.status_code} - 尝试其他字段名...")
        # Try to find the right field
        resp2 = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": f"project={PROJECT_KEY}", "maxResults": 5},
            timeout=30)
        if resp2.status_code == 200:
            for i in resp2.json().get("issues", []):
                fields = i.get("fields", {})
                for k, v in fields.items():
                    if k.startswith("customfield_") and v is not None and "控制" in str(v).lower():
                        print(f"  {i['key']}: {k} = {v}")


def fetch_issues():
    jql = f'project={PROJECT_KEY} AND assignee="{ASSIGNEE}"'
    cf_jql = f' AND "{CONTROLLER_FIELD}" ~ "{CONTROLLER_VALUE}"'

    all_issues = []
    start_at = 0
    max_results = 100
    fields = ("summary,status,priority,assignee,reporter,created,updated,"
              "resolutiondate,issuetype,labels,components,fixVersions,duedate,"
              "customfield_10500")

    # 先试不加控制器过滤
    print(f"  JQL: {jql}")
    resp = session.get(f"{JIRA_URL}/rest/api/2/search",
        params={"jql": jql, "maxResults": 0}, timeout=30)
    resp.raise_for_status()
    total = resp.json().get("total", 0)
    print(f"  不加控制器: {total} 条")

    if total == 0:
        print("  ⚠️ 0 条结果，可能是经办人名称不对，试试 --diag 诊断")
        return []

    # 加控制器
    try:
        jql_full = jql + cf_jql
        print(f"  加控制器: {jql_full}")
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql_full, "maxResults": 0}, timeout=30)
        resp.raise_for_status()
        total2 = resp.json().get("total", 0)
        print(f"  加控制器后: {total2} 条")
    except:
        print(f"  控制器过滤失败，退回不过滤模式")
        total2 = 0

    final_jql = jql if total2 == 0 else jql_full

    while True:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": final_jql, "startAt": start_at, "maxResults": max_results, "fields": fields},
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)
        print(f"  已拉取 {len(all_issues)} / {data.get('total','?')} 条...")
        if start_at + max_results >= data.get("total", 0):
            break
        start_at += max_results

    print(f"✅ 共拉取 {len(all_issues)} 条")
    return all_issues


def push_to_server(issues):
    payload = {
        "project": PROJECT_KEY,
        "fetched_at": datetime.now().isoformat(),
        "total": len(issues),
        "issues": issues,
    }
    resp = requests.post(SERVER_URL, json=payload, timeout=60)
    resp.raise_for_status()
    print(f"✅ 已推送到服务器")


if __name__ == "__main__":
    if "--diag" in sys.argv:
        diag()
        sys.exit(0)

    print(f"🚀 Jira 数据采集 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   项目: {PROJECT_KEY} | 经办人: {ASSIGNEE} | 控制器: {CONTROLLER_VALUE}")
    issues = fetch_issues()
    if issues:
        push_to_server(issues)
    print("🎉 完成！")
