"""
Jira 日报生成+推送 v3 — 视觉/健康检测 拆开发送
从原文件提取密钥
"""
import json, os, requests, re, time
from collections import Counter
from datetime import datetime

DATA_DIR = "/root/jira_agent/data"

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

JOKES = [
    "王晓宾（宾哥）死后被埋了三天，家人听到地底下传来敲击声。众人惊惧，挖开一看，宾哥长叹一口气说：「妈的，棺材里WiFi信号太差了，Jira那个bug我还没修完。」",
    "王晓宾死于高空坠落。警方调查发现，他是被bug气到跳楼的。确认方式：死亡时手里还攥着手机，屏幕上写着『又是健康检测误报』。",
    "宾哥死了，全组开了一个retrospective。Sprint retro结论：宾哥的逝去是一个known issue，won't fix。",
    "任建华死后去见阎王。阎王说：「你生前造了太多bug，要下十八层地狱。」建华跪下求饶：「阎王饶命，我不是故意的，是产品经理需求没写清楚。」阎王一查，还真是。",
    "宾哥死于脑溢血。遗言是：「那个hardcode...改掉...改掉...」最后用力地伸出手指，握住了建华的手。建华：「宾哥我一定改...你的代码我没权限。」",
    "Eric死的时候手里还攥着MacBook，屏幕亮着。法医凑近一看——Safari正在加载Jira，转了36个小时还没打开。Eric的遗言写在浏览器地址栏：「操你妈的Jira服务器。」",
    "王晓宾、任建华和Eric三个人一起去地狱报到。阎王翻着Jira backlog说：「你们仨的bug加起来比我地狱里的冤魂还多。正好，地狱最近在搞敏捷转型，你们就来当scrum master吧。第一个sprint——把奈何桥上排队的鬼按优先级分好。」宾哥当场又死了一次。",
    "任建华进了火葬场，烧到一半炉子报警了。工人打开一看，建华身上的bug backlog太沉，烧不透。工人说：「这得加钱，超重了。」",
    "Eric临死前对宾哥说：「我这辈子最骄傲的事，就是一次code review都没被人骂过。」宾哥说：「废话，你他妈从来不做code review。」Eric咽气了。",
    "王晓宾下地狱第一件事——问阎王WiFi密码。阎王说：「地狱没有WiFi，只有内网。而且只能访问Jira。」宾哥说：「那我这是回家了啊。」",
    "任建华去阎王殿报到，阎王看了看他的简历：「任建华，原商汤科技，主要技能——把bug从open改成won't fix。」建华：「你怎么知道？」阎王：「你组的bug report我这儿都有备份。」",
    "Eric在ICU昏迷了三天，心电监护仪突然响起警报。护士冲进来发现Eric在说梦话：「fuck... the sprint... is ending...」护士看了看Jira，默默把他的氧气拔了。",
    "王晓宾和Eric在坟地里聊天。宾哥问：「你后悔什么？」Eric说：「后悔没在死之前把王晓宾的权限收回。妈的现在他在天上还在往我名下assign bug。」",
    "任建华死后，宾哥提议给他搞个技术分享追悼会。主题：《任建华留下的十个未关闭bug及其对后世的影响》。Eric：「可以，但谁来讲？」宾哥指了指棺材：「让他自己来讲，PPT我帮他做。」",
    "Eric死后魂灵漂到了海底光缆旁边，发现有网。大喜之下掏出手机连上Jira，发现建华刚刚又assign了三个bug给他。Eric把光缆拔了。全球断网三小时。",
    "王晓宾在阎王殿排号，前面还有三百多人。宾哥急了，找阎王插队。阎王说：「你什么理由？」宾哥说：「我Jira上还有个Highest的bug没修。」阎王看了看屏幕：「你那个bug从2023年就挂在那了，多等几辈子无所谓。」",
    "任建华临终前最后一条飞书消息发给宾哥：「宾哥，bug我都修完了。」宾哥正准备感动，点开一看，建华把所有bug的assignee都改成了Eric。",
    "Eric在火化的时候，骨灰里检测出了高浓度的焦虑和骂人话。火化工说：「这辈子没见过谁的骨灰里含有这么多fuck。」",
    "王晓宾、任建华、Eric三个人在地狱开stand-up。宾哥：「昨天干了什么——死了。」建华：「今天计划干什么——继续死。」Eric：「blocker是什么——被你们俩的bug砸死了。」Scrum master阎王：「OK，下一个sprint目标：投胎。」",
    "Eric去看望病危的宾哥。宾哥握着Eric的手：「帮我...把那个...内存泄漏...修了...」Eric含泪点头：「一定。」宾哥死后Eric打开代码一看——整个项目都是内存泄漏。Eric把repo删了。",
    "任建华在地狱食堂吃饭，发现菜里全是bug。投诉给阎王，阎王说：「这里的bug都是你生前写的。自己写的bug，跪着也要吃完。」",
    "王晓宾死后变成了一只鬼，每天晚上飘回公司加班。保安问为什么不去投胎，宾哥说：「投胎了谁修bug？你们以为这项目能自己跑起来？」保安沉默片刻：「宾哥，你死了之后项目已经砍了。」宾哥当场魂飞魄散。",
    "Eric的墓志铭只有一行字：Here lies Eric. Status: Closed. Resolution: Won't Fix.",
    "任建华在孟婆桥上喝孟婆汤。孟婆说：「喝完这碗汤，前尘往事一笔勾销。」建华喝完问：「那我修的那些bug？」孟婆：「那些不算前尘往事，算刑事案底。」",
    "王晓宾、任建华、Eric三人在望乡台上往下看。宾哥：「看，那是咱们的工位，灯还亮着。」建华：「那是有人在加班修我们留下的bug。」Eric：「别傻了，那灯是声控的，从来没关过。」",
    "宾哥死了以后，他老婆翻他手机，发现最后一条微信发给Eric：「兄弟，帮我看看这个crash，我跑了好久没复现。」Eric秒回：「你死了就复现了，这叫reproduce by death。」",
    "任建华的葬礼上，牧师问：「有人想说什么吗？」Eric站起来：「建华是个好人，好同事，但他把我的核心模块重构了一个屎山，我恨他。」说完坐下。全场沉默。牧师：「阿门。」",
    "王晓宾在天堂门口被拦住了。天使说：「你bug太多，不能进。」宾哥急了：「我修了一辈子bug！」天使翻了翻记录：「你修了17个，写了两千多个。门在那边。」指向地狱。宾哥看到建华和Eric已经在里面朝他挥手了。",
    "Eric的鬼魂每天晚上十二点准时出现在公司的Jira服务器上，自动给所有慢查询加索引。运维以为闹鬼了，找道士做法。道士看了看日志：「不是鬼，是Eric。给他烧个16寸MacBook Pro他就安息了。」",
    "任建华在奈何桥上走了一半突然停下。鬼差催他，建华说：「等等，我在看桥的承重计算。这结构不太对，可能是个bug。」鬼差一把推他下去：「你他妈都死了还写code review comment。」"
    "",
    "宾哥写了个语音控制部署的脚本，让讯飞识别「上线」指令，结果讯飞听成「上香」。宾哥看着服务器上自动生成的葬礼流程页面和火葬场预约确认短信，沉默了——讯飞甚至贴心地把哀乐设成了系统BGM。",
    "建华提交了个修复空指针的PR，Eric发现他把所有null检查全改成了try-except pass。建华说不报错不就完了，Eric回那你以后体检也别抽血了指标全是pass不就完了。第二天建华真的没来上班。",
    "Eric凌晨三点还在改bug，宾哥路过看了一眼说别改了这bug三年前就是我写的能跑到今天说明业务根本不依赖这段代码。Eric当场把代码删了，第二天整个支付系统挂了——原来业务三年来全靠这个bug活着。",
    "讯飞智能客服被部署到了殡仪馆预约系统，家属打电话说我爸走了被识别成我爸遛了，客服回复别着急遛完就回来了。家属又打了一遍讯飞识别成再见，客服回复好的再见请给五星好评。",
    "建华给数据库写了个清理过期数据的定时任务，where条件写漏了，半夜跑完发现全公司三年的数据都没了。宾哥问备份呢，建华说备份脚本也是我写的也漏了where条件。两人对望一眼同时开始更新简历。"




]


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
            "is_health": "健康检测" in fld.get("summary", ""),
        }
    return prev


def build_category_report(issues, prev_map, category_name, emoji, is_health=False):
    """为单个分类生成报告"""

    # 当前
    curr = {}
    for i in issues:
        fld = i.get("fields", {})
        curr[i["key"]] = {
            "status": fld.get("status", {}).get("name", ""),
            "priority": (fld.get("priority") or {}).get("name", "-"),
            "summary": fld.get("summary", "")[:80],
            "is_health": is_health,
        }

    # 只看同分类的上次数据
    prev_cat = {k: v for k, v in prev_map.items() if v.get("is_health") == is_health}

    new_issues = [k for k in curr if k not in prev_cat]
    resolved = [k for k in prev_cat if k not in curr]
    changed = []
    for k in set(curr) & set(prev_cat):
        if curr[k]["status"] != prev_cat[k]["status"]:
            changed.append((k, prev_cat[k]["status"], curr[k]["status"]))
        elif curr[k]["priority"] != prev_cat[k]["priority"]:
            changed.append((k, f"P:{prev_cat[k]['priority']}", f"P:{curr[k]['priority']}"))

    sevs = Counter(curr[k]["priority"] for k in curr)
    prio_line = "  ".join(f"{PRIO_EMOJI.get(k, '⚪')}{k}:{c}" for k, c in sevs.most_common())

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        f"{emoji} E0V Jira {category_name}日报",
        f"🕐 {now}",
        f"",
    ]

    # 变化摘要
    if prev_map:
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

    lines.extend([
        f"",
        f"{category_name} | 待处理 {len(curr)} 条 | {prio_line}",
        f"",
    ])

    # 新增
    if new_issues:
        lines.append(f"── 🆕 新增 ({len(new_issues)}条) ──")
        for k in sorted(new_issues, key=lambda x: curr[x]["priority"], reverse=True):
            c = curr[k]
            lines.append(f"[{k}](https://yfjira.mychery.com/browse/{k}) {c['status']} {PRIO_EMOJI.get(c['priority'],'')}")
            lines.append(f"   {c['summary']}")
        lines.append("")

    # 状态变更
    if changed:
        lines.append(f"── 🔄 状态变更 ({len(changed)}条) ──")
        for k, old_s, new_s in changed[:10]:
            c = curr.get(k, {})
            lines.append(f"[{k}](https://yfjira.mychery.com/browse/{k}) {old_s} → {new_s}")
            lines.append(f"   {c.get('summary','?')}")
        if len(changed) > 10:
            lines.append(f"   ...共{len(changed)}条")
        lines.append("")

    # 已解决
    if resolved:
        lines.append(f"── ✅ 已解决 ({len(resolved)}条) ──")
        for k in sorted(resolved)[:8]:
            p = prev_cat.get(k, {})
            lines.append(f"   [{k}](https://yfjira.mychery.com/browse/{k}) {p.get('summary','?')[:60]}")
        lines.append("")

    # 全量待处理
    lines.append(f"── 📋 待处理全览 ({len(curr)}条) ──")
    lines.append("")
    prio_order = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3}
    sorted_issues = sorted(issues, key=lambda i: prio_order.get(curr[i["key"]]["priority"], 99))

    for idx, i in enumerate(sorted_issues, 1):
        k = i["key"]
        c = curr[k]
        tag = " NEW" if k in new_issues else ""
        chg_mark = ""
        for ck, old_s, new_s in changed:
            if ck == k: chg_mark = f" [{old_s}→{new_s}]"; break
        marker = f"{tag}{chg_mark}" if (tag or chg_mark) else ""
        lines.append(f"{idx}. [{k}](https://yfjira.mychery.com/browse/{k}) {c['status']} {PRIO_EMOJI.get(c['priority'],'')}{marker} {c['summary'][:55]}")

    return "\n".join(lines)


def main():
    import random

    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("jira_") and f.endswith(".json")], reverse=True)
    if not files:
        print("❌ 无数据")
        return

    with open(os.path.join(DATA_DIR, files[0])) as f:
        data = json.load(f)
    now_active = get_active_issues(data.get("issues", []))

    prev_data = files[1] if len(files) > 1 else None
    prev_file = os.path.join(DATA_DIR, prev_data) if prev_data else None
    prev = load_previous_active(prev_file)

    visual_issues = [i for i in now_active if "健康检测" not in i.get("fields", {}).get("summary", "")]
    health_issues = [i for i in now_active if "健康检测" in i.get("fields", {}).get("summary", "")]

    # 视觉报告
    visual_report = build_category_report(visual_issues, prev, "视觉", "👁️", is_health=False)

    # 健康检测报告
    health_report = build_category_report(health_issues, prev, "健康检测", "💊", is_health=True)

    # 汇总彩蛋
    joke = random.choice(JOKES)
    visual_report += f"\n\n──\n💀 {joke}"
    health_report += f"\n\n──\n💀 {joke}"

    # 群聊推送 — 分开发送，间隔2秒避免飞书合并
    print(f"👁️ 视觉 ({len(visual_issues)}条)")
    r1 = send_feishu(visual_report, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID)
    print(f"  群: {'✅' if r1.get('code')==0 else '❌ '+r1.get('msg','')}")

    time.sleep(2)

    print(f"💊 健康检测 ({len(health_issues)}条)")
    r2 = send_feishu(health_report, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID)
    print(f"  群: {'✅' if r2.get('code')==0 else '❌ '+r2.get('msg','')}")

    # 个人推送（合并发送）
    combined = f"{visual_report}\n\n{'='*30}\n\n{health_report}"
    r3 = send_feishu(combined, PERSONAL_APP_ID, PERSONAL_APP_SECRET, PERSONAL_OPEN_ID, "open_id")
    print(f"  个人: {'✅' if r3.get('code')==0 else '❌ '+r3.get('msg','')}")


if __name__ == "__main__":
    main()
