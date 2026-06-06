"""
Jira AI 根因分析引擎 v2
- 两级分类：大类(视觉/健康检测) → 小类(DMS/OMS/Linux/Service/UI/协议/数据…)
- 精简根因（每条<80字）
- 大日志分段分析
- 记忆库持久化
"""
import json, os, re
from datetime import datetime
from collections import Counter, defaultdict
import requests

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = "sk-d507c4ac5b464286b2b975b7629d13d4"
MODEL = "deepseek-chat"

DATA_DIR = "/root/jira_agent/data"
MEMORY_DIR = "/root/jira_agent/memory"
TEMP_DIR = "/tmp/jira_analysis"
MAX_CHUNK = 25000
MAX_LOG = 80000

os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ── LLM ────────────────────────────────────────────────

def call_llm(messages, max_tokens=1500, temperature=0.3):
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ── 日志处理 ───────────────────────────────────────────

def extract_logs_from_attachments(attachments):
    logs = []
    for att in attachments:
        filename = att.get("filename", "")
        content = att.get("content", "")
        if not content:
            continue
        import base64
        try:
            raw = base64.b64decode(content)
        except:
            raw = content.encode() if isinstance(content, str) else content

        if filename.lower().endswith(".zip"):
            try:
                import zipfile, io
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        try:
                            text = zf.read(name).decode("utf-8", errors="replace")
                            logs.append(f"--- {filename}/{name} ---\n{text[:MAX_LOG]}")
                        except:
                            pass
            except:
                logs.append(f"[{filename} 解压失败]")
        elif any(filename.lower().endswith(e) for e in [".log", ".txt", ".text", ".out"]):
            try:
                logs.append(f"--- {filename} ---\n{raw.decode('utf-8', errors='replace')[:MAX_LOG]}")
            except:
                pass
        else:
            logs.append(f"[附件: {filename} ({len(raw)} bytes)]")
    return logs


def chunk_text(text, max_chars=MAX_CHUNK):
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


# ── 单 Case 分析 ───────────────────────────────────────

SUB_CATEGORIES = {
    "视觉": ["DMS", "OMS", "Linux", "Service", "UI渲染", "协议通信", "数据同步", "人脸识别", "账户登录", "仪表显示", "系统设置", "音频", "其他"],
    "健康检测": ["数据采集", "算法模型", "UI渲染", "蓝牙/WiFi", "协议通信", "数据同步", "账户登录", "其他"],
}

ANALYSIS_PROMPT = """你是汽车电子座舱域控制器(ICC)测试专家。分析以下 Jira Case，输出精简 JSON。

## Case
- Key: {key} | 状态: {status} | 优先级: {priority}
- 标题: {summary}
- 描述: {desc}
- 评论: {comments}

## 日志
{logs}

## 输出要求
1. 必须先判断大类: "视觉" 或 "健康检测"
2. 再判断小类。视觉可选: DMS/OMS/Linux/Service/UI渲染/协议通信/数据同步/人脸识别/账户登录/仪表显示/系统设置/音频/其他
   健康检测可选: 数据采集/算法模型/UI渲染/蓝牙WiFi/协议通信/数据同步/账户登录/其他
3. 根因每条不超过80字，只说最可能的技术原因
4. 建议修复定位到具体模块/接口/文件

```json
{{
  "main_category": "视觉",
  "sub_category": "DMS",
  "symptom": "一句话(<40字)",
  "root_causes": [
    {{"cause": "<80字精简根因>", "probability": "高/中/低", "evidence": "日志/描述证据<50字"}}
  ],
  "suggested_fix": "建议<100字",
  "severity": "高/中/低",
  "key_finding": "<40字核心发现"
}}
```"""


def analyze_single_issue(issue, logs):
    key = issue.get("key", "?")
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    description = issue.get("_description", fields.get("description", "")) or ""
    comments = issue.get("_comments", fields.get("comment", {}).get("comments", []))
    status = fields.get("status", {}).get("name", "?")
    priority = fields.get("priority", {}).get("name", "-")

    # 评论压缩
    comment_text = ""
    for c in (comments or [])[:5]:
        author = c.get("author", {}).get("displayName", "?")
        body = c.get("body", "")[:300]
        comment_text += f"[{author}]: {body}\n"

    # 日志处理
    log_text = "\n".join(logs) if logs else "(无日志)"
    if len(log_text) > MAX_CHUNK * 1.5:
        chunks = chunk_text(log_text)
        summaries = []
        for i, ch in enumerate(chunks):
            p = f"总结日志片段{i+1}/{len(chunks)}，提取错误码/异常堆栈/时序异常/状态机异常：\n{ch[:MAX_CHUNK]}"
            try:
                s = call_llm([{"role": "user", "content": p}], max_tokens=400)
                summaries.append(s)
            except:
                summaries.append(f"[片段{i+1}分析失败]")
        log_text = "=== 日志分段总结 ===\n" + "\n".join(summaries)

    prompt = ANALYSIS_PROMPT.format(
        key=key, status=status, priority=priority,
        summary=summary[:200], desc=(description or "")[:500],
        comments=comment_text[:500],
        logs=log_text[:4000],
    )

    try:
        result = call_llm([{"role": "user", "content": prompt}], max_tokens=1000)
        m = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        return json.loads(m.group(1)) if m else json.loads(result)
    except:
        return {
            "main_category": "视觉", "sub_category": "其他",
            "symptom": summary[:40],
            "root_causes": [{"cause": "AI分析未完成", "probability": "低", "evidence": ""}],
            "suggested_fix": "需人工分析", "severity": "中", "key_finding": "分析未完成",
        }


# ── 聚类 ───────────────────────────────────────────────

def cluster_analyses(analyses):
    # 一级聚类
    by_main = defaultdict(lambda: defaultdict(list))
    for a in analyses:
        mc = a.get("main_category", "视觉")
        sc = a.get("sub_category", "其他")
        by_main[mc][sc].append(a)

    # 热点
    cause_groups = defaultdict(list)
    for a in analyses:
        for rc in a.get("root_causes", []):
            c = rc.get("cause", "")
            if len(c) > 15:
                cause_groups[c[:40]].append(a.get("_key"))

    hot_spots = []
    for cause, keys in cause_groups.items():
        if len(set(keys)) >= 2:
            hot_spots.append({"pattern": cause, "count": len(set(keys)), "keys": list(set(keys))[:5]})

    return {
        "by_main": {mc: dict(sc) for mc, sc in by_main.items()},
        "hot_spots": sorted(hot_spots, key=lambda x: -x["count"]),
    }


# ── 记忆 ───────────────────────────────────────────────

def load_memory():
    path = os.path.join(MEMORY_DIR, "issue_history.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"issues": {}, "last_updated": None}


def save_memory(memory):
    memory["last_updated"] = datetime.now().isoformat()
    with open(os.path.join(MEMORY_DIR, "issue_history.json"), "w") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def update_memory(key, analysis, issue):
    mem = load_memory()
    now = datetime.now().isoformat()
    if key not in mem["issues"]:
        mem["issues"][key] = {"first_seen": now, "occurrences": [], "main_cats": [], "sub_cats": []}
    e = mem["issues"][key]
    e.setdefault("main_cats", [])
    e.setdefault("sub_cats", [])
    e["occurrences"].append({
        "time": now,
        "status": issue.get("fields", {}).get("status", {}).get("name", "?"),
        "main_cat": analysis.get("main_category", "视觉"),
        "sub_cat": analysis.get("sub_category", "其他"),
        "severity": analysis.get("severity", "中"),
    })
    if analysis.get("main_category") not in e["main_cats"]:
        e["main_cats"].append(analysis["main_category"])
    if analysis.get("sub_category") not in e["sub_cats"]:
        e["sub_cats"].append(analysis["sub_category"])
    save_memory(mem)
    return mem


# ── 全量分析 ───────────────────────────────────────────

def run_full_analysis(data_file=None):
    if data_file:
        with open(data_file) as f:
            data = json.load(f)
    else:
        files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("jira_") and f.endswith(".json")], reverse=True)
        if not files:
            return {"error": "无数据"}
        with open(os.path.join(DATA_DIR, files[0])) as f:
            data = json.load(f)

    issues = data.get("issues", [])
    analyses = []
    i = 0

    for idx, issue in enumerate(issues):
        key = issue.get("key", "?")
        fields = issue.get("fields", {})
        status = fields.get("status", {}).get("name", "")
        if status not in {"已分配", "分析中", "修复中"}:
            continue

        # 控制器过滤
        from src.analyzer import parse_customfield, CONTROLLER_VALUE as CV
        cf = parse_customfield(fields.get("customfield_10500", ""))
        if CV not in cf:
            continue
        i += 1

        summary = fields.get("summary", "")
        print(f"  [{i}] {key} {summary[:40]}...")

        # 日志
        atts = issue.get("_attachments", [])
        logs = extract_logs_from_attachments(atts) if atts else []

        # LLM分析
        analysis = analyze_single_issue(issue, logs)
        analysis["_key"] = key
        analysis["_status"] = status
        analysis["_summary"] = summary
        analysis["_priority"] = fields.get("priority", {}).get("name", "-")
        analyses.append(analysis)

        update_memory(key, analysis, issue)

    clusters = cluster_analyses(analyses)

    result = {
        "time": datetime.now().isoformat(),
        "total_analyzed": len(analyses),
        "clusters": clusters,
        "analyses": analyses,
    }

    path = os.path.join(DATA_DIR, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(analyses)} 条 | 大类: {list(clusters['by_main'].keys())} | 热点: {len(clusters['hot_spots'])}")
    return result


if __name__ == "__main__":
    run_full_analysis()
