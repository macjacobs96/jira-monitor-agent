"""
飞书云文档报告生成器 v3
- 只用 text + heading2 block（已验证可行）
- 两级分类排版：视觉/健康检测 大类 → 子类
- 精简格式，单一文档
"""
import json, os, requests, sys, time
from datetime import datetime
from collections import defaultdict, Counter

sys.path.insert(0, "/root/jira_agent")

FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"


def get_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    return resp.json()["tenant_access_token"]


def create_doc(title):
    token = get_token()
    resp = requests.post(
        "https://open.feishu.cn/open-apis/docx/v1/documents",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title}, timeout=15)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建文档失败: {data.get('msg')}")
    return data["data"]["document"]["document_id"]


def append_blocks(doc_id, blocks):
    """分批追加 block，每批最多 40 个"""
    token = get_token()
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i + 40]
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"children": batch, "index": -1}, timeout=30)
        d = resp.json()
        if d.get("code") != 0:
            print(f"  ⚠️ 批次 {i//40+1} 失败: {d.get('msg','?')[:80]}")
            return False
        time.sleep(0.3)
    return True


def B(text, bold=False):
    """创建文本 block"""
    els = [{"text_run": {"content": text}}]
    if bold:
        els = [{"text_run": {"content": text, "text_element_style": {"bold": True}}}]
    return {"block_type": 2, "text": {"elements": els, "style": {}}}


def H2(text):
    """创建 H2 标题"""
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": text}}], "style": {}}}


def EMPTY():
    """空行"""
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}], "style": {}}}


def SEP():
    """分隔行"""
    return B("━━━━━━━━━━━━━━━━━━━━━━━━━━")


def build_report(result, project="E0V"):
    analyses = result.get("analyses", [])
    clusters = result.get("clusters", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    by_main = clusters.get("by_main", {})
    vis_cases = sum(len(v) for v in by_main.get("视觉", {}).values()) if "视觉" in by_main else 0
    health_cases = sum(len(v) for v in by_main.get("健康检测", {}).values()) if "健康检测" in by_main else 0
    hot_spots = clusters.get("hot_spots", [])

    b = []

    # ── 标题 ──
    b.append(H2(f"📊 {project} Jira AI 根因分析报告"))
    b.append(B(f"🕐 {now}  |  分析 {len(analyses)} 条待处理 Case  |  👁️视觉 {vis_cases}  💊健康检测 {health_cases}"))
    b.append(EMPTY())

    # ── 概览 ──
    b.append(B("📈 分类概览", bold=True))

    for mc in ["视觉", "健康检测"]:
        if mc not in by_main:
            continue
        emoji = "👁️" if mc == "视觉" else "💊"
        scs = by_main[mc]
        total_mc = sum(len(v) for v in scs.values())
        b.append(B(f"{emoji} {mc}（{total_mc} 条）", bold=True))
        for sc in sorted(scs.keys(), key=lambda k: -len(scs[k])):
            items = scs[sc]
            keys = [a.get("_key") for a in items[:5]]
            more = f" +{len(items)-5}条" if len(items) > 5 else ""
            sev = Counter(a.get("severity", "?") for a in items)
            sev_str = " ".join(f"{k}×{c}" for k, c in sev.most_common())
            b.append(B(f"  ▸ {sc}：{len(items)}条 ({sev_str})  {', '.join(keys)}{more}"))
        b.append(EMPTY())

    # 热点
    if hot_spots:
        b.append(B("🔥 根因热点", bold=True))
        for hs in hot_spots[:5]:
            b.append(B(f"  ▸ {hs['pattern']} — 涉及 {hs['count']} 个 Case"))
        b.append(EMPTY())

    b.append(SEP())
    b.append(EMPTY())

    # ── 逐 Case ──
    b.append(B("📋 逐 Case 根因分析", bold=True))
    b.append(EMPTY())

    # 排序
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
            b.append(B(f"【{sc}】（{len(items)}条）", bold=True))

            for a in items:
                idx += 1
                key = a["_key"]
                sev = a.get("severity", "?")

                # Case 标题
                b.append(B(f"#{idx}  {key}  [{sev}]  {a.get('symptom','')[:60]}"))

                # 根因（精简）
                for rc in a.get("root_causes", [])[:2]:
                    p = rc.get("probability", "?")
                    c = rc.get("cause", "")[:80]
                    b.append(B(f"     [{p}] {c}"))

                # 建议
                fix = a.get("suggested_fix", "")
                if fix:
                    b.append(B(f"     🔧 {fix[:100]}"))

                b.append(EMPTY())

    b.append(SEP())
    b.append(B("🤖 本报告由 AI 自动生成，分析仅供参考，请结合实车验证。"))
    return b


def send_text(text):
    token = get_token()
    requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": FEISHU_CHAT_ID, "msg_type": "text",
              "content": json.dumps({"text": text})}, timeout=15)


def create_and_push(analysis_file=None, project="E0V"):
    """主流程"""
    if analysis_file:
        with open(analysis_file) as f:
            result = json.load(f)
    else:
        files = sorted(
            [f for f in os.listdir("/root/jira_agent/data")
             if f.startswith("analysis_") and f.endswith(".json")], reverse=True)
        if not files:
            send_text("⚠️ 无分析数据")
            return None
        with open(os.path.join("/root/jira_agent/data", files[0])) as f:
            result = json.load(f)

    total = result.get("total_analyzed", 0)
    if total == 0:
        send_text("📊 今日无待处理 Case，AI 分析报告跳过 🎉")
        return None

    # 构建
    blocks = build_report(result, project)
    print(f"📝 {len(blocks)} blocks")

    # 创建文档
    title = f"{project} AI 根因分析 — {datetime.now().strftime('%m/%d %H:%M')}"
    print(f"📄 {title}")
    doc_id = create_doc(title)

    # 写入
    ok = append_blocks(doc_id, blocks)
    doc_link = f"https://bytedance.feishu.cn/docx/{doc_id}"

    if ok:
        by_main = result["clusters"].get("by_main", {})
        vis_n = sum(len(v) for v in by_main.get("视觉", {}).values()) if "视觉" in by_main else 0
        health_n = sum(len(v) for v in by_main.get("健康检测", {}).values()) if "健康检测" in by_main else 0
        hot_n = len(result["clusters"].get("hot_spots", []))

        send_text(
            f"🧠 {project} AI 根因分析报告\n"
            f"📊 {total} 条 | 👁️视觉 {vis_n} | 💊健康检测 {health_n}\n"
            f"🔥 热点 {hot_n} 个\n"
            f"📄 {doc_link}"
        )
        print(f"✅ {doc_link}")
    else:
        send_text(f"⚠️ 文档部分写入失败\n📄 {doc_link}")

    return doc_link


if __name__ == "__main__":
    create_and_push()
