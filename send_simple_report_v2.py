"""
Jira 日报生成+推送 v2 — 增量对比
从原文件提取密钥，避免 exec 执行
"""
import json, os, requests, re
from collections import Counter
from datetime import datetime

DATA_DIR = "/root/jira_agent/data"

# 从原文件提取密钥（正则，不 exec）
def _extract_var(path, varname):
    with open(path) as f:
        content = f.read()
    m = re.search(rf'{varname}\s*=\s*"([^"]+)"', content)
    if m: return m.group(1)
    raise ValueError(f"未找到 {varname}")

ORIG = "/root/jira_agent/send_simple_report.py"
FEISHU_APP_ID = _extract_var(ORIG, "FEISHU_APP_ID")
FEISHU_APP_SECRET = _extract_var(ORIG, "FEISHU_APP_SECRET")
FEISHU_CHAT_ID = _extract_var(ORIG, "FEISHU_CHAT_ID")
PERSONAL_APP_ID = _extract_var(ORIG, "PERSONAL_APP_ID")
PERSONAL_APP_SECRET = _extract_var(ORIG, "PERSONAL_APP_SECRET")
PERSONAL_OPEN_ID = _extract_var(ORIG, "PERSONAL_OPEN_ID")

CONTROLLER_VALUE = "ICC-视觉"
ACTIVE_STATUSES = {"已分配", "分析中", "修复中", "验收中", "处理中", "挂起", "申请挂起中"}
CLOSED_STATUSES = {"完成", "已关闭", "已解决"}
PRIO_EMOJI = {"Highest": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}


def parse_cf(val):
    if val is None: return ""
    if isinstance(val, dict): return val.get("value", val.get("name", str(val)))
    if isinstance(val, list):
        return ", ".join(v.get("value", v.get("name", str(v))) if isinstance(v, dict) else str(v) for v in val)
    return str(val)


def get_token(app_id, app_secret):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    return resp.json().get("tenant_access_token", "")


def send_feishu(text, app_id, app_secret, target, target_type="chat_id"):
    token = get_token(app_id, app_secret)
    return requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={target_type}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": target, "msg_type": "text", "content": json.dumps({"text": text})},
        timeout=15).json()


def get_active_issues(issues):
    active = []
    for i in issues:
        cf = parse_cf(i.get("fields", {}).get("customfield_10500", ""))
        if CONTROLLER_VALUE not in cf: continue
        status = i.get("fields", {}).get("status", {}).get("name", "")
        if status not in ACTIVE_STATUSES: continue
        active.append(i)
    seen = {i["key"] for i in active}
    for i in issues:
        if i["key"] in seen: continue
        summary = i.get("fields", {}).get("summary", "")
        if "健康检测" not in summary: continue
        status = i.get("fields", {}).get("status", {}).get("name", "")
        if status in CLOSED_STATUSES: continue
        active.append(i)
    return active


def load_previous_active(prev_file):
    if not prev_file: return {}
    try:
        with open(prev_file) as f:
            data = json.load(f)
    except: return {}
    prev = {}
    for i in get_active_issues(data.get("issues", [])):
        fld = i.get("fields", {})
        prev[i["key"]] = {
            "status": fld.get("status", {}).get("name", ""),
            "priority": (fld.get("priority") or {}).get("name", "-"),
            "summary": fld.get("summary", "")[:80],
            "updated": fld.get("updated", ""),
            "is_health": "健康检测" in fld.get("summary", ""),
        }
    return prev


def build_delta_report():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("jira_") and f.endswith(".json")], reverse=True)
    if not files: return None

    with open(os.path.join(DATA_DIR, files[0])) as f:
        data = json.load(f)
    now_active = get_active_issues(data.get("issues", []))

    prev_data = files[1] if len(files) > 1 else None
    prev_file = os.path.join(DATA_DIR, prev_data) if prev_data else None
    prev = load_previous_active(prev_file)

    curr = {}
    for i in now_active:
        fld = i.get("fields", {})
        curr[i["key"]] = {
            "status": fld.get("status", {}).get("name", ""),
            "priority": (fld.get("priority") or {}).get("name", "-"),
            "summary": fld.get("summary", "")[:80],
            "updated": fld.get("updated", ""),
            "is_health": "健康检测" in fld.get("summary", ""),
        }

    new_issues = [k for k in curr if k not in prev]
    resolved = [k for k in prev if k not in curr]
    changed = []
    for k in set(curr) & set(prev):
        if curr[k]["status"] != prev[k]["status"]:
            changed.append((k, prev[k]["status"], curr[k]["status"]))
        elif curr[k]["priority"] != prev[k]["priority"]:
            changed.append((k, f"P:{prev[k]['priority']}", f"P:{curr[k]['priority']}"))

    visual = [i for i in now_active if not curr[i["key"]]["is_health"]]
    health = [i for i in now_active if curr[i["key"]]["is_health"]]
    sevs = Counter(curr[k]["priority"] for k in curr)

    lines = [
        f"📊 E0V Jira 待处理日报",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    if prev:
        delta_parts = []
        if new_issues: delta_parts.append(f"🆕新增{len(new_issues)}")
        if resolved: delta_parts.append(f"✅解决{len(resolved)}")
        if changed: delta_parts.append(f"🔄变更{len(changed)}")
        if delta_parts:
            lines.append(f"📈 自上次: {' | '.join(delta_parts)}")
        else:
            lines.append(f"📈 自上次: 无变化")
    else:
        lines.append(f"📈 首次报告")

    prio_line = "  ".join(f"{PRIO_EMOJI.get(k, '⚪')}{k}:{c}" for k, c in sevs.most_common())
    lines.extend([
        f"",
        f"ICC-视觉 | 待处理 {len(now_active)} 条 | {prio_line}",
        f"👁️视觉{len(visual)} 💊健康检测{len(health)}",
        f"",
    ])

    if new_issues:
        lines.append(f"── 🆕 新增 ({len(new_issues)}条) ──")
        for k in sorted(new_issues, key=lambda x: curr[x]["priority"], reverse=True):
            c = curr[k]
            e = "💊" if c["is_health"] else "👁️"
            lines.append(f"{e} [{k}](https://yfjira.mychery.com/browse/{k}) {c['status']} {PRIO_EMOJI.get(c['priority'],'')}")
            lines.append(f"   {c['summary']}")
        lines.append("")

    if changed:
        lines.append(f"── 🔄 状态变更 ({len(changed)}条) ──")
        for k, old_s, new_s in changed[:10]:
            c = curr.get(k, {})
            e = "💊" if c.get("is_health") else "👁️"
            lines.append(f"{e} [{k}](https://yfjira.mychery.com/browse/{k}) {old_s} → {new_s}")
            lines.append(f"   {c.get('summary','?')}")
        if len(changed) > 10:
            lines.append(f"   ...共{len(changed)}条")
        lines.append("")

    if resolved:
        lines.append(f"── ✅ 已解决 ({len(resolved)}条) ──")
        for k in sorted(resolved)[:8]:
            p = prev.get(k, {})
            lines.append(f"   [{k}](https://yfjira.mychery.com/browse/{k}) {p.get('summary','?')[:60]}")
        lines.append("")

    lines.append(f"── 📋 待处理全览 ({len(now_active)}条) ──")
    lines.append("")
    prio_order = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3}
    sorted_active = sorted(now_active, key=lambda i: (curr[i["key"]]["is_health"], prio_order.get(curr[i["key"]]["priority"], 99)))

    for idx, i in enumerate(sorted_active, 1):
        k = i["key"]
        c = curr[k]
        e = "💊" if c["is_health"] else "👁️"
        tag = " NEW" if k in new_issues else ""
        chg_mark = ""
        for ck, old_s, new_s in changed:
            if ck == k: chg_mark = f" [{old_s}→{new_s}]"; break
        marker = f"{tag}{chg_mark}" if (tag or chg_mark) else ""
        lines.append(f"{idx}. [{k}](https://yfjira.mychery.com/browse/{k}) {c['status']} {PRIO_EMOJI.get(c['priority'],'')}{marker} {c['summary'][:55]}")

    lines.append("")
    lines.append("──")
    import random
    jokes = [
        "王晓宾（宾哥）死后被埋了三天，家人听到地底下传来敲击声。众人惊惧，挖开一看，宾哥长叹一口气说：「妈的，棺材里WiFi信号太差了，Jira那个bug我还没修完。」",
        "王晓宾死于高空坠落。警方调查发现，他是被bug气到跳楼的。确认方式：死亡时手里还攥着手机，屏幕上写着『又是健康检测误报』。",
        "宾哥死了，全组开了一个retrospective。Sprint retro结论：宾哥的逝去是一个known issue，won't fix。",
        "任建华死后去见阎王。阎王说：「你生前造了太多bug，要下十八层地狱。」建华跪下求饶：「阎王饶命，我不是故意的，是产品经理需求没写清楚。」阎王一查，还真是。",
        "宾哥死于脑溢血。遗言是：「那个hardcode...改掉...改掉...」最后用力地伸出手指，握住了建华的手。建华：「宾哥我一定改...你的代码我没权限。」",
    "",
    "",
    "宾哥写了个语音控制部署的脚本，让讯飞识别「上线」指令，结果讯飞听成「上香」。宾哥看着服务器上自动生成的葬礼流程页面和火葬场预约确认短信，沉默了——讯飞甚至贴心地把哀乐设成了系统BGM。",
    "建华提交了个修复空指针的PR，Eric发现他把所有null检查全改成了try-except pass。建华说不报错不就完了，Eric回那你以后体检也别抽血了指标全是pass不就完了。第二天建华真的没来上班。",
    "Eric凌晨三点还在改bug，宾哥路过看了一眼说别改了这bug三年前就是我写的能跑到今天说明业务根本不依赖这段代码。Eric当场把代码删了，第二天整个支付系统挂了——原来业务三年来全靠这个bug活着。",
    "讯飞智能客服被部署到了殡仪馆预约系统，家属打电话说我爸走了被识别成我爸遛了，客服回复别着急遛完就回来了。家属又打了一遍讯飞识别成再见，客服回复好的再见请给五星好评。",
    "建华给数据库写了个清理过期数据的定时任务，where条件写漏了，半夜跑完发现全公司三年的数据都没了。宾哥问备份呢，建华说备份脚本也是我写的也漏了where条件。两人对望一眼同时开始更新简历。"



    ]
    lines.append(f"💀 {random.choice(jokes)}")
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_delta_report()
    if report:
        print(report[:300])
        print("...")
        print("\n📤 群聊...")
        r = send_feishu(report, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID)
        print(f"  {'✅' if r.get('code')==0 else '❌ '+r.get('msg','')}")
        r2 = send_feishu(report, PERSONAL_APP_ID, PERSONAL_APP_SECRET, PERSONAL_OPEN_ID, "open_id")
        print(f"  个人 {'✅' if r2.get('code')==0 else '❌ '+r2.get('msg','')}")
    else:
        print("❌ 无数据")
