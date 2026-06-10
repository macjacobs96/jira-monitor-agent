"""
Jira 数据采集脚本 — 服务器版（通过 frp 代理访问内网 Jira）
用法: python3 jira_fetcher_server.py
     python3 jira_fetcher_server.py --no-analyze   # 只拉数据不分析
     python3 jira_fetcher_server.py --diag          # 诊断连接
"""
import requests, json, sys, os, io, zipfile, time
from datetime import datetime

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

# frp 代理：通过 Mac 隧道访问内网 Jira
JIRA_URL = "https://localhost:18443"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
PROJECT_KEY = "E0V"
ASSIGNEE = "商 汤API"
CONTROLLER_FIELD = "customfield_10500"
CONTROLLER_VALUE = "ICC-视觉"

DATA_DIR = "/root/jira_agent/data"
os.makedirs(DATA_DIR, exist_ok=True)

MAX_ATTACH_SIZE = 5 * 1024 * 1024      # 单附件最大 5MB
TOTAL_ATTACH_LIMIT = 20 * 1024 * 1024  # 总附件限制 20MB

# ── Session ────────────────────────────────────────────

session = requests.Session()
session.auth = (JIRA_USER, JIRA_PASS)
session.verify = False  # frp 隧道 TLS 证书域名不匹配（localhost vs yfjira.mychery.com）
session.headers.update({
    "Accept": "application/json",
    "Host": "yfjira.mychery.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})

# 禁 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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

        if filename.lower().endswith(".zip"):
            results = []
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        try:
                            text = zf.read(name).decode("utf-8", errors="replace")
                            results.append(f"--- {name} ---\n{text[:200000]}")
                        except:
                            results.append(f"[{name} 无法解码]")
                return {"filename": filename, "content": "\n".join(results), "size": size}
            except Exception as e:
                return {"filename": filename, "content": f"[解压失败: {e}]", "size": size}

        try:
            text = raw.decode("utf-8", errors="replace")
            return {"filename": filename, "content": text[:200000], "size": size}
        except:
            return {"filename": filename, "content": f"[{len(raw)} bytes 二进制]", "size": size}

    except Exception as e:
        return {"filename": filename, "content": f"[下载异常: {e}]", "size": 0}


# ── 主采集流程 ──────────────────────────────────────────

def fetch_issues_basic():
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
        print("⚠️ 控制器过滤失败，退回不过滤")
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
    enriched = []
    total_attach = 0
    for idx, issue in enumerate(issues):
        key = issue.get("key", "?")
        status = issue.get("fields", {}).get("status", {}).get("name", "")

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

        issue["_description"] = details.get("description", "")
        issue["_comments"] = details.get("comments", [])
        issue["_attachments"] = att_contents

        enriched.append(issue)
        print(f"✅ {len(att_contents)} 个附件 ({total_attach/1024/1024:.1f}MB累计)")

    return enriched


def save_data(issues):
    payload = {
        "project": PROJECT_KEY,
        "fetched_at": datetime.now().isoformat(),
        "total": len(issues),
        "issues": issues,
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(DATA_DIR, f"jira_{ts}.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存 {len(issues)} 条 → {path}")
    return path


# ── 诊断 ────────────────────────────────────────────────

def diag():
    print("🔍 frp 代理诊断\n")
    print(f"   目标: {JIRA_URL}")
    print(f"   项目: {PROJECT_KEY}")
    print(f"   经办人: {ASSIGNEE}\n")

    # 1. 连通性
    print("📡 测试连通性...")
    try:
        resp = session.get(f"{JIRA_URL}/rest/api/2/serverInfo", timeout=10)
        print(f"   HTTP {resp.status_code}")
        if resp.status_code == 200:
            info = resp.json()
            print(f"   Jira 版本: {info.get('version','?')}")
            print(f"   ✅ 连通正常！")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        print("\n   可能原因:")
        print("   1. Mac 端 frpc 未启动")
        print("   2. Mac 网络无法访问 Jira")
        print("   3. Mac 防火墙阻止了 frpc")
        return

    # 2. 查询测试
    print(f"\n📋 查询测试...")
    try:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": f"project={PROJECT_KEY}", "maxResults": 1, "fields": "summary"},
            timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            issues = data.get("issues", [])
            sample = issues[0]["key"] if issues else "N/A"
            print(f"   项目 {PROJECT_KEY}: {total} 条 (示例: {sample})")
    except Exception as e:
        print(f"   ❌ {e}")


# ══════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--diag" in sys.argv:
        diag()
        sys.exit(0)

    do_analyze = "--no-analyze" not in sys.argv

    print(f"🚀 Jira 服务器版采集 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   代理: {JIRA_URL} | 项目: {PROJECT_KEY} | 经办人: {ASSIGNEE}\n")

    # Step 1: 基础列表
    print("📋 Step 1: 拉取基础列表...")
    try:
        issues = fetch_issues_basic()
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        print("   请确认 Mac 端 frpc 已启动: ./frpc -c frpc.toml")
        sys.exit(1)

    print(f"   共 {len(issues)} 条\n")

    # Step 2: 增强数据
    print("📎 Step 2: 拉取详情和附件...")
    issues = enrich_issues(issues)
    print()

    # Step 3: 保存本地
    print("💾 Step 3: 保存数据...")
    data_path = save_data(issues)

    # Step 4: AI 分析（服务器本地执行）
    if do_analyze:
        print("\n🧠 Step 4: AI 根因分析...")
        import threading
        def analyze_and_report():
            try:
                from ai_analyzer import run_full_analysis, cleanup_temp
                from prd_scope import enrich_analysis_with_scope
                from dual_report import dual_output

                print(f"[AI] 开始分析 {data_path}")
                result = run_full_analysis(data_file=data_path)
                total = result.get("total_analyzed", 0)

                if total > 0:
                    print(f"[AI] {total} 条根因分析完成，PRD 范围判定...")
                    result = enrich_analysis_with_scope(result)
                    scope = result.get("scope_summary", {})
                    print(f"[AI] PRD内:{scope.get('in_scope',0)} PRD外:{scope.get('out_of_scope',0)}")
                    print(f"[AI] 推送双输出报告...")
                    dual_output()
                    print(f"[AI] 报告已推送")
                else:
                    print("[AI] 今日无待处理 Case")

                cleanup_temp()
            except Exception as e:
                print(f"[AI] 分析失败: {e}")
                import traceback
                traceback.print_exc()

        t = threading.Thread(target=analyze_and_report, daemon=True)
        t.start()
        print("   AI 分析已启动（后台运行）")

    print("\n🎉 采集完成！")
