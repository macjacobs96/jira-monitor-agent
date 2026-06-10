"""
Jira Agent HTTP 服务 v2 —— 接收客户端推送、AI 根因分析、飞书云文档报告
"""
import json
import os
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

sys.path.insert(0, "/root/jira_agent")
from src.analyzer import save_snapshot, load_latest, analyze, format_report

# 飞书 Jira日报助手
FEISHU_APP_ID = "cli_aaabea78707a5ce2"
FEISHU_APP_SECRET = "qYiWvXFnmQEaN66FiBvoOg34uVGzcaQe"
FEISHU_CHAT_ID = "oc_321e2187f4d599c9c0156bd09b133d93"

DATA_DIR = "/root/jira_agent/data"
ICC_WEEKLY_DIR = "/root/jira_agent/data/icc_weekly"
PORT = 80

os.makedirs(ICC_WEEKLY_DIR, exist_ok=True)


def save_icc_weekly(payload):
    """保存 ICC 周报数据"""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(ICC_WEEKLY_DIR, f"icc_weekly_{ts}.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def get_feishu_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10,
    )
    return resp.json().get("tenant_access_token", "")


def send_feishu(text):
    token = get_feishu_token()
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "receive_id": FEISHU_CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
        timeout=15,
    )
    return resp.json()


def run_ai_analysis_async(data_path):
    """后台线程：运行 AI 分析 → 生成报告（优先飞书文档，兜底群发）"""
    try:
        from ai_analyzer import run_full_analysis, cleanup_temp
        from prd_scope import enrich_analysis_with_scope
        from dual_report import dual_output

        print(f"[AI] 开始根因分析 {data_path}")
        result = run_full_analysis(data_file=data_path)
        total = result.get("total_analyzed", 0)

        if total > 0:
            print(f"[AI] {total} 条根因分析完成，开始 PRD 范围判定...")
            result = enrich_analysis_with_scope(result)
            scope = result.get("scope_summary", {})
            print(f"[AI] PRD内:{scope.get('in_scope',0)} PRD外:{scope.get('out_of_scope',0)} 模糊:{scope.get('borderline',0)}")
            print(f"[AI] 推送双输出报告...")
            dual_output()
            print(f"[AI] 报告已推送")
        else:
            send_feishu("📊 今日无待处理 Case，不生成 AI 分析报告 🎉")
            print("[AI] 无需分析，跳过")

        cleanup_temp()
    except Exception as e:
        print(f"[AI] 分析失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_feishu(f"⚠️ AI 分析异常: {str(e)[:100]}")
        except:
            pass


class JiraHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif self.path == "/api/jira/report":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","message":"use POST to trigger report"}')
        elif self.path == "/jira_fetcher_v2.py":
            # 直接返回脚本内容，方便本地 curl 下载
            script_path = os.path.join(os.path.dirname(__file__), "jira_fetcher_v2.py")
            try:
                with open(script_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # ── 旧端点 (v1 兼容) ──
        if self.path == "/api/jira/sync":
            try:
                payload = json.loads(body)
                path = save_snapshot(payload)
                print(f"[{datetime.now():%H:%M:%S}] 收到 {payload.get('total', 0)} 条, 保存至 {path}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "count": payload.get("total", 0),
                    "saved": os.path.basename(path),
                }).encode())
            except Exception as e:
                print(f"错误: {e}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        # ── AI 分析端点 ──
        elif self.path == "/api/jira/analyze":
            try:
                payload = json.loads(body)
                path = save_snapshot(payload)
                print(f"[{datetime.now():%H:%M:%S}] 收到 {payload.get('total', 0)} 条 (v2增强), 保存至 {path}")

                # 后台运行 AI 分析
                do_analyze = payload.get("analyze", True)
                if do_analyze:
                    t = threading.Thread(target=run_ai_analysis_async, args=(path,), daemon=True)
                    t.start()
                    msg = "AI 分析已启动，结果将通过飞书文档推送"
                else:
                    msg = "数据已保存（跳过 AI 分析）"

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "count": payload.get("total", 0),
                    "saved": os.path.basename(path),
                    "analyzing": do_analyze,
                    "message": msg,
                }).encode())
            except Exception as e:
                print(f"错误: {e}")
                import traceback
                traceback.print_exc()
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        # ── 手动触发日报 ──
        elif self.path == "/api/jira/report":
            data = load_latest()
            if data:
                result = analyze(data)
                report = format_report(result)
                resp = send_feishu(report)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "feishu_response": resp,
                }).encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "无数据"}).encode())

        # ── ICC 视觉验收中周报接收 ──
        elif self.path == "/api/jira/icc-weekly":
            try:
                payload = json.loads(body)
                path = save_icc_weekly(payload)
                print(f"[{datetime.now():%H:%M:%S}] ICC周报收到 {payload.get('total', 0)} 条, 保存至 {path}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "count": payload.get("total", 0),
                    "week": f"{payload.get('week_start','?')} ~ {payload.get('week_end','?')}",
                    "saved": os.path.basename(path),
                }).encode())
            except Exception as e:
                print(f"ICC周报错误: {e}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')

    def log_message(self, format, *args):
        pass  # 静默


def main():
    print(f"🚀 Jira Agent v2 启动 :{PORT}")
    print(f"   端点: /api/jira/sync  /api/jira/analyze  /api/jira/report")
    print(f"   数据: {DATA_DIR}")
    print(f"   飞书: {FEISHU_CHAT_ID}")
    server = HTTPServer(("0.0.0.0", PORT), JiraHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 关闭")
        server.server_close()


if __name__ == "__main__":
    main()
