"""
Feishu Bot Webhook
"""
import json, os, hashlib, re, requests, urllib3, time
from flask import Flask, request, jsonify
urllib3.disable_warnings()
app = Flask(__name__)
X1 = "cli_aab932ce3779dce1"
X2 = "Hgp5WqvlgpiDqzOCfY5lxhBzSG2L52pa"
X3 = "oc_12669ad6501c1eb7ec0f2820ccc3d4b0"
JIRA_URL = "https://localhost:18443"
JIRA_USER = "senseautoAPI"
JIRA_PASS = "senseautoAPI33@"
jira_session = requests.Session()
jira_session.auth = (JIRA_USER, JIRA_PASS)
jira_session.verify = False
jira_session.headers.update({"Host": "yfjira.mychery.com", "Accept": "application/json"})
HELP = """Bot Jira AI Agent
@Bot chaxun <Jira>  — chaxun dan Issue
@Bot sousuo <guanjianci> — sou ICC-AI
@Bot bangzhu — xianshi bangzhu"""
def get_token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", json={"app_id": X1, "app_secret": X2}, timeout=10)
    return r.json().get("tenant_access_token", "")
def reply(msg_id, text):
    token = get_token()
    return requests.post(f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"content": json.dumps({"text": text}), "msg_type": "text"}, timeout=15).json()
def search_issues(keyword, max_results=10):
    jql = f'project=E0V AND labels=ICC-AI AND labels=商汤Agent AND (summary ~ "{keyword}" OR description ~ "{keyword}")'
    r = jira_session.get(f"{JIRA_URL}/rest/api/2/search", params={"jql": jql, "maxResults": max_results, "fields": "summary,status,priority,assignee,updated"}, timeout=15)
    r.raise_for_status()
    return r.json()
def get_issue(key):
    r = jira_session.get(f"{JIRA_URL}/rest/api/2/issue/{key}", params={"fields": "summary,status,priority,assignee,created,updated,description,comment"}, timeout=15)
    r.raise_for_status()
    return r.json()
def fmt(issue):
    f = issue.get("fields", {})
    k = issue["key"]
    return f"Jira [{k}](https://yfjira.mychery.com/browse/{k})\nStatus: {f.get('status',{}).get('name','?')} | P: {(f.get('priority') or {}).get('name','-')} | Assignee: {(f.get('assignee') or {}).get('displayName','-')} | Updated: {f.get('updated','')[:16]}\nSummary: {f.get('summary','?')}"
def parse_cmd(text):
    text = re.sub(r'@\S+\s*', '', text).strip()
    if not text or text in ("help", "bangzhu"): return "help", ""
    if m := re.match(r'(cha(xun)?|get|lookup)\s*([A-Z]+-\d+)', text, re.I): return "get", m.group(3).upper()
    if m := re.match(r'(sou(suo)?|search|find)\s*(.+)', text): return "search", m.group(3).strip()
    return "search", text
@app.route("/feishu/webhook", methods=["POST"])
def webhook():
    body = request.get_json(force=True, silent=True) or {}
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})
    event = body.get("event", {})
    header = body.get("header", {})
    if header.get("event_type") != "im.message.receive_v1":
        return jsonify({"code": 0})
    msg = event.get("message", {})
    if msg.get("message_type") != "text":
        return jsonify({"code": 0})
    if not msg.get("mentions"):
        return jsonify({"code": 0})
    text = json.loads(msg.get("content", "{}")).get("text", "")
    action, arg = parse_cmd(text)
    try:
        if action == "help":
            reply(msg["message_id"], HELP)
        elif action == "get":
            reply(msg["message_id"], fmt(get_issue(arg)))
        elif action == "search":
            r = search_issues(arg)
            issues = r.get("issues", [])
            if not issues:
                reply(msg["message_id"], f"No results for: {arg}")
            else:
                out = [f"Search: {arg} ({len(issues)} found, {r.get('total',0)} total):", ""]
                for i in issues[:8]:
                    out.append(fmt(i))
                    out.append("")
                reply(msg["message_id"], "\n".join(out))
    except Exception as e:
        reply(msg["message_id"], f"Error: {str(e)[:200]}")
    return jsonify({"code": 0})
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8899, debug=False)
