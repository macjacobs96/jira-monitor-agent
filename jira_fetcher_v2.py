"""
Jira 数据采集脚本 v2 —— AI 根因分析增强版
新增: Issue 详情(描述+评论) + 附件下载(log/zip解压)
用法: python3 jira_fetcher_v2.py
"""
import requests, json, sys, os, io, zipfile, base64, tempfile, shutil
from datetime import datetime

JIRA_URL = "https://yfjira.mychery.com"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
PROJECT_KEY = "E0V"
ASSIGNEE = "商 汤API"
CONTROLLER_FIELD = "customfield_10500"
CONTROLLER_VALUE = "ICC-视觉"
SERVER_URL = "http://43.159.43.36/api/jira/analyze"  # 新端点

session = requests.Session()
session.auth = (JIRA_USER, JIRA_PASS)
session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
session.verify = False  # 公司内网可能有证书问题
requests.packages.urllib3.disable_warnings()

MAX_ATTACH_SIZE = 5 * 1024 * 1024  # 单附件最大 5MB
TOTAL_ATTACH_LIMIT = 20 * 1024 * 1024  # 总附件限制 20MB


# ── Issue 详情获取 ──────────────────────────────────────

def fetch_issue_details(issue_key):
    """获取单个 Issue 的完整详情（描述 + 评论 + 附件）"""
    resp = session.get(
        f"{JIRA_URL}/rest/api/2/issue/{issue_key}",
        params={"fields": "description,comment,attachment"},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"description": "", "comments": [], "attachments": []}

    fields = resp.json().get("fields", {})
    return {
        "description": fields.get("description", ""),
        "comments": fields.get("comment", {}).get("comments", []),
        "attachments": fields.get("attachment", []),
    }


def download_attachment(att, issue_key):
    """下载单个附件，文本类读取内容，zip 解压提取"""
    content_url = att.get("content", "")
    filename = att.get("filename", "")
    size = att.get("size", 0)
    mime = att.get("mimeType", "")

    if size > MAX_ATTACH_SIZE:
        return {"filename": filename, "content": f"[文件过大 {size/1024/1024:.1f}MB, 跳过]", "size": size}

    # 关心日志/文本/zip 类附件
    interested = any(
        filename.lower().endswith(ext) or t in (mime or "").lower()
        for ext in [".log", ".txt", ".text", ".zip", ".gz", ".out", ".csv", ".json"]
        for t in ["text/plain", "application/zip", "application/gzip", "text/csv", "application/json"]
    )

    if not interested:
        return {"filename": filename, "content": f"[{mime} 附件, {size} bytes]", "size": size}

    try:
        resp = session.get(content_url, timeout=30)
        if resp.status_code != 200:
            return {"filename": filename, "content": f"[下载失败 HTTP {resp.status_code}]", "size": 0}

        raw = resp.content

        # ZIP 解压
        if filename.lower().endswith(".zip"):
            results = []
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        try:
                            text = zf.read(name).decode("utf-8", errors="replace")
                            results.append(f"--- {name} ---\n{text[:200000]}")  # 最多20万字符
                        except:
                            results.append(f"[{name} 无法解码]")
                return {"filename": filename, "content": "\n".join(results), "size": size}
            except Exception as e:
                return {"filename": filename, "content": f"[解压失败: {e}]", "size": size}

        # 纯文本
        try:
            text = raw.decode("utf-8", errors="replace")
            return {"filename": filename, "content": text[:200000], "size": size}
        except:
            return {"filename": filename, "content": f"[{len(raw)} bytes 二进制]", "size": size}

    except Exception as e:
        return {"filename": filename, "content": f"[下载异常: {e}]", "size": 0}


# ── 主采集流程 ──────────────────────────────────────────

def fetch_issues_basic():
    """拉取基础列表（与 v1 相同）"""
    jql = f'project={PROJECT_KEY} AND assignee="{ASSIGNEE}"'
    cf_jql = f' AND "{CONTROLLER_FIELD}" ~ "{CONTROLLER_VALUE}"'

    all_issues = []
    start_at = 0
    max_results = 100
    fields = ("summary,status,priority,assignee,reporter,created,updated,"
              "resolutiondate,issuetype,labels,components,fixVersions,duedate,"
              "customfield_10500")

    try:
        jql_full = jql + cf_jql
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql_full, "maxResults": 0}, timeout=30)
        resp.raise_for_status()
    except:
        jql_full = jql

    while True:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": jql_full, "startAt": start_at, "maxResults": max_results, "fields": fields},
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)
        if start_at + max_results >= data.get("total", 0):
            break
        start_at += max_results

    return all_issues


def enrich_issues(issues):
    """为每个 Issue 拉取详情和附件"""
    enriched = []
    total_attach = 0
    for idx, issue in enumerate(issues):
        key = issue.get("key", "?")
        status = issue.get("fields", {}).get("status", {}).get("name", "")

        # 跳过快关闭的
        if status in ["已关闭", "已解决", "完成"]:
            enriched.append(issue)
            print(f"  [{idx+1}/{len(issues)}] {key} ⏭️ 已关闭,跳过")
            continue

        print(f"  [{idx+1}/{len(issues)}] {key} 📥 拉取详情...", end=" ")

        try:
            details = fetch_issue_details(key)
        except Exception as e:
            print(f"⚠️ 详情失败: {e}")
            enriched.append(issue)
            continue

        # 下载附件
        att_contents = []
        for att in details.get("attachments", []):
            if total_attach >= TOTAL_ATTACH_LIMIT:
                break
            try:
                result = download_attachment(att, key)
                att_contents.append(result)
                total_attach += att.get("size", 0)
            except Exception as e:
                att_contents.append({"filename": att.get("filename", ""), "content": f"[下载失败: {e}]"})

        # 注入增强数据
        issue["_description"] = details.get("description", "")
        issue["_comments"] = details.get("comments", [])
        issue["_attachments"] = att_contents

        enriched.append(issue)
        print(f"✅ {len(att_contents)} 个附件 ({total_attach/1024/1024:.1f}MB累计)")

    return enriched


def push_to_server(issues):
    """推送到服务器 AI 分析端点"""
    payload = {
        "project": PROJECT_KEY,
        "fetched_at": datetime.now().isoformat(),
        "total": len(issues),
        "issues": issues,
        "analyze": True,  # 触发 AI 分析
    }

    print(f"📤 推送 {len(issues)} 条到 {SERVER_URL}...")
    resp = requests.post(SERVER_URL, json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()
    print(f"✅ 服务器响应: {result.get('status', '?')}")
    return result


# ── 入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🚀 Jira AI 分析采集 v2 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   {PROJECT_KEY} | {ASSIGNEE} | {CONTROLLER_VALUE}\n")

    # Step 1: 基础列表
    print("📋 Step 1: 拉取基础列表...")
    issues = fetch_issues_basic()
    print(f"   共 {len(issues)} 条\n")

    # Step 2: 增强数据
    print("📎 Step 2: 拉取详情和附件...")
    issues = enrich_issues(issues)
    print()

    # Step 3: 推送服务器
    print("📤 Step 3: 推送服务器 AI 分析...")
    result = push_to_server(issues)

    print("\n🎉 完成！AI 分析中，稍后查看飞书推送。")
