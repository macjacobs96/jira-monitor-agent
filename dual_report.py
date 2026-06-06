"""
双输出报告生成器
- 格式1: 飞书群文本日报（不变，每日两次）
- 格式2: 飞书云文档（含 PRD 范围分析 + 根因）
"""
import json, os, requests, time
from datetime import datetime
from collections import defaultdict, Counter

FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"
DATA_DIR = "/root/jira_agent/data"


def get_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    return resp.json()["tenant_access_token"]


def load_latest_analysis():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("analysis_") and f.endswith(".json")], reverse=True)
    if not files:
        return None
    with open(os.path.join(DATA_DIR, files[0])) as f:
        return json.load(f)


# ═══════════════════════════════════════════════
# 格式1：文本日报（不变）
# ═══════════════════════════════════════════════

def send_text(text):
    token = get_token()
    requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": FEISHU_CHAT_ID, "msg_type": "text",
              "content": json.dumps({"text": text})}, timeout=15)


def format_daily_text(result, project="E0V"):
    """格式1：简洁文本日报"""
    analyses = result.get("analyses", [])
    scope = result.get("scope_summary", {})
    clusters = result.get("clusters", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(analyses)
    in_scope = scope.get("in_scope", total)
    out_scope = scope.get("out_of_scope", 0)

    lines = [
        f"📊 {project} Jira 日报",
        f"🕐 {now}  |  待处理 **{total}** 条",
        f"",
        f"✅ PRD范围内: {in_scope}  |  ❌ 范围外: {out_scope}",
        f"",
    ]

    # 按大类简列
    by_main = clusters.get("by_main", {})
    for mc in ["视觉", "健康检测"]:
        if mc not in by_main:
            continue
        emoji = "👁️" if mc == "视觉" else "💊"
        scs = by_main[mc]
        total_mc = sum(len(v) for v in scs.values())
        lines.append(f"{emoji} {mc}（{total_mc}条）")
        for sc in sorted(scs.keys(), key=lambda k: -len(scs[k])):
            items = scs[sc]
            keys = [a.get("_key") for a in items[:3]]
            more = f" +{len(items)-3}" if len(items) > 3 else ""
            lines.append(f"  ▸ {sc}: {', '.join(keys)}{more}")
        lines.append("")

    # 不在PRD的提示
    if out_scope > 0:
        out_list = scope.get("out_of_scope_list", [])
        lines.append(f"⚠️ 不在PRD范围: {', '.join(out_list[:5])}")

    lines.append(f"---\n📄 详细分析见飞书云文档")

    return "\n".join(lines)


# ═══════════════════════════════════════════════
# 格式2：飞书云文档（PRD范围 + 根因）
# ═══════════════════════════════════════════════

def B(text, bold=False):
    els = [{"text_run": {"content": text}}]
    if bold:
        els[0]["text_run"]["text_element_style"] = {"bold": True}
    return {"block_type": 2, "text": {"elements": els, "style": {}}}


def H2(text):
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": text}}], "style": {}}}


def EMPTY():
    return B("")


def SEP():
    return B("━━━━━━━━━━━━━━━━━━━━━━")


def create_doc(title):
    token = get_token()
    r = requests.post("https://open.feishu.cn/open-apis/docx/v1/documents",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title}, timeout=15)
    return r.json()["data"]["document"]["document_id"]


def append_blocks(doc_id, blocks):
    token = get_token()
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i + 40]
        r = requests.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"children": batch, "index": -1}, timeout=30)
        d = r.json()
        if d.get("code") != 0:
            print(f"  ⚠️ 批次{i//40+1}: {d.get('msg','?')[:60]}")
            return False
        time.sleep(0.3)
    return True


def build_cloud_doc(result, project="E0V"):
    """格式2：飞书云文档 —— 含PRD范围分析"""
    analyses = result.get("analyses", [])
    scope = result.get("scope_summary", {})
    clusters = result.get("clusters", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(analyses)
    in_scope = scope.get("in_scope", total)
    out_scope = scope.get("out_of_scope", 0)
    borderline = scope.get("borderline", 0)

    b = []

    # ── 标题 ──
    b.append(H2(f"📊 {project} Jira AI 分析 + PRD 范围报告"))
    b.append(B(f"🕐 {now}  |  分析 {total} 条待处理  |  ✅PRD内 {in_scope}  ❌PRD外 {out_scope}  ⚠️模糊 {borderline}"))
    b.append(EMPTY())

    # ── PRD 范围概览 ──
    b.append(B("📋 PRD 范围判定", bold=True))
    b.append(B(f"  ✅ 在PRD范围内: {in_scope} 条 — 属于我方交付功能"))
    b.append(B(f"  ❌ 不在PRD范围: {out_scope} 条 — 需确认是否我方问题"))
    b.append(B(f"  ⚠️ 模糊/待确认: {borderline} 条"))
    b.append(EMPTY())

    # 不在范围内的列出
    out_list = scope.get("out_of_scope_list", [])
    borderline_list = scope.get("borderline_list", [])
    if out_list:
        b.append(B("❌ 不在PRD范围的Case：", bold=True))
        for key in out_list[:10]:
            a = next((x for x in analyses if x.get("_key") == key), None)
            if a:
                reason = a.get("scope_reason", "")
                b.append(B(f"  ▸ {key}: {a.get('_summary','')[:50]}"))
                b.append(B(f"    判定: {reason[:80]}"))
        b.append(EMPTY())
    if borderline_list:
        b.append(B("⚠️ 模糊/待确认：", bold=True))
        for key in borderline_list:
            a = next((x for x in analyses if x.get("_key") == key), None)
            if a:
                b.append(B(f"  ▸ {key}: {a.get('scope_reason','')[:80]}"))
        b.append(EMPTY())

    b.append(SEP())
    b.append(EMPTY())

    # ── 分类概览 ──
    b.append(B("📈 分类概览（PRD内 Case）", bold=True))
    by_main = clusters.get("by_main", {})
    for mc in ["视觉", "健康检测"]:
        if mc not in by_main:
            continue
        emoji = "👁️" if mc == "视觉" else "💊"
        scs = by_main[mc]
        total_mc = sum(len(v) for v in scs.values())
        # 只计算PRD内的
        in_scope_items = {sc: [a for a in items if a.get("scope") == "in_scope"] for sc, items in scs.items()}
        in_scope_count = sum(len(v) for v in in_scope_items.values())
        out_count = total_mc - in_scope_count
        b.append(B(f"{emoji} {mc}：{total_mc}条（✅PRD内 {in_scope_count} / ❌PRD外 {out_count}）", bold=True))
        for sc in sorted(scs.keys(), key=lambda k: -len(scs[k])):
            items = scs[sc]
            in_count = len([a for a in items if a.get("scope") == "in_scope"])
            out_in_cat = len(items) - in_count
            keys = [a.get("_key") for a in items[:4]]
            more = f" +{len(items)-4}" if len(items) > 4 else ""
            mark = ""
            if out_in_cat > 0:
                mark = f" ⚠️{out_in_cat}条不在PRD"
            b.append(B(f"  ▸ {sc}：{len(items)}条（✅{in_count} PRD内）{mark}  {', '.join(keys)}{more}"))
        b.append(EMPTY())

    b.append(SEP())
    b.append(EMPTY())

    # ── 逐 Case 详情 ──
    b.append(B("📋 逐 Case 分析（仅 PRD 范围内）", bold=True))
    b.append(EMPTY())

    by_cat = defaultdict(lambda: defaultdict(list))
    for a in analyses:
        by_cat[a.get("main_category", "视觉")][a.get("sub_category", "其他")].append(a)

    idx = 0
    for mc in ["视觉", "健康检测"]:
        if mc not in by_cat:
            continue
        emoji = "👁️" if mc == "视觉" else "💊"
        b.append(SEP())
        b.append(B(f"{emoji} {mc}", bold=True))
        b.append(EMPTY())

        for sc in sorted(by_cat[mc].keys(), key=lambda k: -len(by_cat[mc][k])):
            items = by_cat[mc][sc]
            # 只展示PRD内的
            in_items = [a for a in items if a.get("scope") == "in_scope"]
            out_items = [a for a in items if a.get("scope") != "in_scope"]

            if in_items:
                b.append(B(f"【{sc}】（{len(in_items)}条，PRD范围内）", bold=True))
                for a in in_items:
                    idx += 1
                    key = a["_key"]
                    sev = a.get("severity", "?")
                    scope_tag = "✅PRD内" if a.get("scope") == "in_scope" else f"⚠️{a.get('scope','')}"

                    b.append(B(f"#{idx}  {key}  [{sev}]  [{scope_tag}]  {a.get('symptom','')[:60]}"))

                    for rc in a.get("root_causes", [])[:2]:
                        b.append(B(f"     [{rc.get('probability','?')}] {rc.get('cause','')[:80]}"))

                    fix = a.get("suggested_fix", "")
                    if fix:
                        b.append(B(f"     🔧 {fix[:100]}"))
                    b.append(EMPTY())

            if out_items:
                b.append(B(f"【{sc}】（{len(out_items)}条，⚠️不在PRD范围）", bold=True))
                for a in out_items:
                    b.append(B(f"  {a['_key']} [{a.get('scope','?')}] {a.get('scope_reason','')[:80]}"))
                b.append(EMPTY())

    b.append(SEP())
    b.append(B("🤖 本报告由 AI 自动生成，分析仅供参考，请结合实车验证。"))
    return b


# ═══════════════════════════════════════════════
# 双输出入口
# ═══════════════════════════════════════════════

def dual_output(project="E0V"):
    """双输出：文本日报 + 云文档"""
    result = load_latest_analysis()
    if not result or result.get("total_analyzed", 0) == 0:
        send_text("📊 今日无待处理 Case 🎉")
        return

    total = result.get("total_analyzed", 0)

    # ── 格式1: 文本日报 ──
    text = format_daily_text(result, project)
    send_text(text)
    print("✅ 格式1: 文本日报已推送")

    # ── 格式2: 云文档 ──
    try:
        blocks = build_cloud_doc(result, project)
        title = f"{project} PRD范围分析 + AI根因 — {datetime.now().strftime('%m/%d %H:%M')}"
        doc_id = create_doc(title)
        ok = append_blocks(doc_id, blocks)
        doc_link = f"https://bytedance.feishu.cn/docx/{doc_id}"

        if ok:
            scope = result.get("scope_summary", {})
            send_text(
                f"📄 {project} PRD范围分析 + AI根因报告\n"
                f"📊 {total}条 | ✅PRD内 {scope.get('in_scope',total)} | ❌PRD外 {scope.get('out_of_scope',0)}\n"
                f"🔗 {doc_link}"
            )
            print(f"✅ 格式2: 云文档 {doc_link}")
        return doc_link
    except Exception as e:
        print(f"⚠️ 云文档失败: {e}")
        return None


if __name__ == "__main__":
    dual_output()
