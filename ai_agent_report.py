"""
AI Agent Jira 日报 — 采集+推送（商汤Agent / 健康智能体）
用法: python3 ai_agent_report.py
"""
import json, os, requests, re, time
from collections import Counter
from datetime import datetime
import urllib3
import random
urllib3.disable_warnings()

# ── 地狱笑话 ──────────────────────────────────────────
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
    "任建华在奈何桥上走了一半突然停下。鬼差催他，建华说：「等等，我在看桥的承重计算。这结构不太对，可能是个bug。」鬼差一把推他下去：「你他妈都死了还写code review comment。」",
    "讯飞死了以后去见阎王。阎王说：「你不是AI公司吗？怎么自己先挂了？」讯飞说：「我语音识别把阎王的'进来'听成了'滚'，就滚了。」阎王：「...这是哪儿的口音问题。」",
    "讯飞心脏病发作送ICU，医生用讯飞语音输入系统记录病历。系统把'心梗'转写成了'新梗'。医生看了看：「没啥事，就是个新段子。」讯飞当场走了。",
    "讯飞死后火化，火葬场的智能语音系统是讯飞做的。火化工喊：「开始火化！」系统：「我没听清，请再说一遍。」火化工：「我说开始火化！！」系统：「正在为您搜索'开十火花'...」",
    "讯飞死了，追悼会上放了一段AI合成的遗言。讯飞的声音从音响里传出来：「感谢大家...今天天气...晴...温度...26度...湿度...」满座沉默。原来他的AI只学会了播天气预报。",
    "讯飞的墓碑上刻了二维码，扫一扫能听到他的AI语音。结果扫出来是：「对不起，我无法理解您的问题。请换一种说法。」",
    "讯飞在ICU病床上问护士：「我还有救吗？」护士用讯飞输入法记录：「我还有救吗」→ 系统输出：「我还有救吗」→ AI助手回复：「根据你的描述，建议你...尽快安排后事。」",
    "讯飞临死前最后一句话是对着手机说的。手机屏幕显示：「正在识别...」「识别失败，请检查网络连接。」讯飞含恨咽气。",
    "讯飞的骨灰盒上印着一行字：'Powered by iFLYTEK —— 语音识别准确率 98%。剩下的 2%，要了你的命。'",
    "讯飞到了阴间，阎王让他登记。讯飞说：「我叫讯飞。」阎王的书记官用讯飞系统录入：「姓名：训飞」。阎王说：「训飞，你生前罪孽深重，下油锅。」讯飞：「我他妈叫讯飞不是训飞！！」",
    "讯飞下地狱，发现地狱的客服系统是自己做的。他对着喇叭喊：「我不想下地狱！」系统：「您好，您说'我想下单一盒月饼'，正在为您处理...」讯飞被推进了油锅。",
    "讯飞在生死簿上签字，手抖。阎王说：「没事，用语音吧。」讯飞说：「我信不过我自己。」阎王：「那你怎么卖出去那么多？」讯飞：「因为我客户都死了。」",
    "讯飞死后第二天，全国所有语音助手同时罢工。用户问：「今天天气怎么样？」助手回答：「他走了...他真的走了...呜呜呜...」举国震惊。原来讯飞把情感模块做到云端了。",
    "讯飞的追悼会直播，AI实时字幕显示：「今天我们怀着沉重的心情...」→ 字幕：「今天我们怀着沉重的星星...」。在线观众：「？」",
    "讯飞在地狱排队投胎，阎王说：「你可以选下辈子做什么。」讯飞说：「我想做个不会被自己产品害死的人。」阎王查了查系统：「这个选项不存在。你要不要考虑做个产品经理？」",
    "讯飞的葬礼上放了一台智能音箱。牧师说：「讯飞，安息吧。」音箱：「好的，已为您播放《安息吧》——正在搜索——抱歉，未找到该歌曲。为您推荐《死了都要爱》。」"
    "",
    "宾哥写了个语音控制部署的脚本，让讯飞识别「上线」指令，结果讯飞听成「上香」。宾哥看着服务器上自动生成的葬礼流程页面和火葬场预约确认短信，沉默了——讯飞甚至贴心地把哀乐设成了系统BGM。",
    "建华提交了个修复空指针的PR，Eric发现他把所有null检查全改成了try-except pass。建华说不报错不就完了，Eric回那你以后体检也别抽血了指标全是pass不就完了。第二天建华真的没来上班。",
    "Eric凌晨三点还在改bug，宾哥路过看了一眼说别改了这bug三年前就是我写的能跑到今天说明业务根本不依赖这段代码。Eric当场把代码删了，第二天整个支付系统挂了——原来业务三年来全靠这个bug活着。",
    "讯飞智能客服被部署到了殡仪馆预约系统，家属打电话说我爸走了被识别成我爸遛了，客服回复别着急遛完就回来了。家属又打了一遍讯飞识别成再见，客服回复好的再见请给五星好评。",
    "建华给数据库写了个清理过期数据的定时任务，where条件写漏了，半夜跑完发现全公司三年的数据都没了。宾哥问备份呢，建华说备份脚本也是我写的也漏了where条件。两人对望一眼同时开始更新简历。"





]

# ── Jira 连接 ──────────────────────────────────────────
JIRA_URL = "https://localhost:18443"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
PROJECT = "E0V"

session = requests.Session()
session.auth = (JIRA_USER, JIRA_PASS)
session.verify = False
session.headers.update({
    "Host": "yfjira.mychery.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
})

# ── 飞书密钥 ──────────────────────────────────────────
ORIG = "/root/jira_agent/send_simple_report.py"
FEISHU_APP_ID = "cli_aab932ce3779dce1"
FEISHU_APP_SECRET="YOUR_FEISHU_APP_SECRET"
FEISHU_CHAT_ID = "oc_12669ad6501c1eb7ec0f2820ccc3d4b0"

# ── 筛选条件 ───────────────────────────────────────────
ACTIVE_STATUSES = {"已分配", "分析中", "修复中", "验收中", "处理中", "挂起", "申请挂起中"}
CLOSED_STATUSES = {"完成", "已关闭", "已解决"}
PRIO_EMOJI = {"Highest": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}

# ICC-AI 控制器(cf[10500]) + 商汤API 经办 + (健康关键词 OR 商汤Agent标签)
JQL = ('project=E0V AND assignee="商 汤API" '
       'AND cf[10500]="ICC-AI" '
       'AND (summary ~ "健康" OR summary ~ "健康智能体" OR labels=商汤Agent)')
FIELDS = "summary,status,priority,labels,assignee,created,updated,customfield_10500"

DATA_DIR = "/root/jira_agent/data_ai_agent"
os.makedirs(DATA_DIR, exist_ok=True)


def get_token(aid, sec):
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": aid, "app_secret": sec}, timeout=10)
    return r.json().get("tenant_access_token", "")


def send_feishu(text, aid, sec, target, tt="chat_id"):
    token = get_token(aid, sec)
    return requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={tt}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": target, "msg_type": "text", "content": json.dumps({"text": text})},
        timeout=15).json()


# ── 采集 ────────────────────────────────────────────────

def fetch_all_issues():
    all_issues = []
    start = 0
    while True:
        resp = session.get(f"{JIRA_URL}/rest/api/2/search",
            params={"jql": JQL, "startAt": start, "maxResults": 100, "fields": FIELDS},
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)
        if start + 100 >= data.get("total", 0):
            break
        start += 100
    return all_issues


def save_data(issues):
    payload = {
        "project": PROJECT,
        "fetched_at": datetime.now().isoformat(),
        "total": len(issues),
        "issues": issues,
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(DATA_DIR, f"ai_agent_{ts}.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# ── 增量对比 ────────────────────────────────────────────

def load_prev():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("ai_agent_") and f.endswith(".json")], reverse=True)
    if len(files) < 2: return {}
    with open(os.path.join(DATA_DIR, files[1])) as f:
        data = json.load(f)
    prev = {}
    for i in data.get("issues", []):
        fld = i.get("fields", {})
        prev[i["key"]] = {
            "status": fld.get("status", {}).get("name", ""),
            "priority": (fld.get("priority") or {}).get("name", "-"),
            "summary": fld.get("summary", ""),
        }
    return prev


def build_report(issues, prev):
    curr = {}
    for i in issues:
        fld = i.get("fields", {})
        curr[i["key"]] = {
            "status": fld.get("status", {}).get("name", ""),
            "priority": (fld.get("priority") or {}).get("name", "-"),
            "summary": fld.get("summary", ""),
        }

    new_issues = [k for k in curr if k not in prev]
    resolved = [k for k in prev if k not in curr]
    changed = []
    for k in set(curr) & set(prev):
        if curr[k]["status"] != prev[k]["status"]:
            changed.append((k, prev[k]["status"], curr[k]["status"]))
        elif curr[k]["priority"] != prev[k]["priority"]:
            changed.append((k, f"P:{prev[k]['priority']}", f"P:{curr[k]['priority']}"))

    sevs = Counter(curr[k]["priority"] for k in curr)
    prio_line = "  ".join(f"{PRIO_EMOJI.get(k, '⚪')}{k}:{c}" for k, c in sevs.most_common())

    lines = [
        f"🤖 E0V AI Agent 日报",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    if prev:
        delta = []
        if new_issues: delta.append(f"🆕新增{len(new_issues)}")
        if resolved: delta.append(f"✅解决{len(resolved)}")
        if changed: delta.append(f"🔄变更{len(changed)}")
        lines.append(f"📈 自上次: {' | '.join(delta)}" if delta else f"📈 自上次: 无变化")
    else:
        lines.append(f"📈 首次报告")

    lines.extend([
        f"",
        f"ICC-AI · 商汤Agent/健康智能体 | 待处理 {len(curr)} 条 | {prio_line}",
        f"经办: 商汤API | 标签: ICC-AI + 商汤Agent",
        f"",
    ])

    # ── 待处理全览（按状态分组，放最前面） ──
    status_order = ["已分配", "分析中", "修复中", "验收中", "处理中", "挂起", "申请挂起中"]
    status_groups = {s: [] for s in status_order}
    for i in issues:
        st = curr[i["key"]]["status"]
        if st in status_groups:
            status_groups[st].append(i)
        else:
            status_groups.setdefault(st, []).append(i)

    for st in status_order + [s for s in status_groups if s not in status_order]:
        group = status_groups.get(st, [])
        if not group: continue
        lines.append(f"── {st} ({len(group)}条) ──")
        for i in group:
            k = i["key"]
            c = curr[k]
            markers = []
            if prev:
                if k in new_issues: markers.append("NEW")
                for ck, old_s, new_s in changed:
                    if ck == k: markers.append(f"{old_s}->{new_s}"); break
            marker = f" {' '.join(markers)}" if markers else ""
            lines.append(f"  [{k}](https://yfjira.mychery.com/browse/{k}) {PRIO_EMOJI.get(c['priority'],'')}{marker} {c['summary']}")
        lines.append("")

    # ── 增量（放后面，有历史才显示） ──
    if not prev:
        lines.append("")
        lines.append("──")
        lines.append(f"💀 {random.choice(JOKES)}")
        return chr(10).join(lines)
    if new_issues:
        lines.append(f"── 🆕 新增 ({len(new_issues)}条) ──")
        for k in sorted(new_issues, key=lambda x: curr[x]["priority"], reverse=True):
            c = curr[k]
            lines.append(f"[{k}](https://yfjira.mychery.com/browse/{k}) {c['status']} {PRIO_EMOJI.get(c['priority'],'')}")
            lines.append(f"   {c['summary']}")
        lines.append("")

    if changed:
        lines.append(f"── 🔄 状态变更 ({len(changed)}条) ──")
        for k, old_s, new_s in changed[:10]:
            c = curr.get(k, {})
            lines.append(f"[{k}](https://yfjira.mychery.com/browse/{k}) {old_s} → {new_s}")
            lines.append(f"   {c.get('summary','?')}")
        lines.append("")

    if resolved:
        lines.append(f"── ✅ 已解决 ({len(resolved)}条) ──")
        for k in sorted(resolved)[:8]:
            p = prev.get(k, {})
            lines.append(f"   [{k}](https://yfjira.mychery.com/browse/{k}) {p.get('summary','?')}")
        lines.append("")

    lines.append("")
    lines.append("──")
    lines.append(f"💀 {random.choice(JOKES)}")
    return chr(10).join(lines)


# ── 主流程 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("📋 采集 AI Agent issues...")
    issues = fetch_all_issues()
    print(f"   共 {len(issues)} 条")
    save_data(issues)

    active = [i for i in issues if i.get("fields", {}).get("status", {}).get("name", "") in ACTIVE_STATUSES]
    print(f"   活跃: {len(active)} 条")

    prev = load_prev()
    report = build_report(active, prev)

    print(f"\n🤖 推送 AI Agent 飞书群...")
    r = send_feishu(report, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID)
    print(f"   {'✅' if r.get('code')==0 else '❌ '+r.get('msg','')}")
