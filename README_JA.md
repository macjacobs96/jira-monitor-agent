<p align="center">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README_EN.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_JA.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README_AR.md">🇸🇦 العربية</a>
</p>

---

# Jira Monitor Agent

> 設定駆動の Jira 課題監視 + 定期 Lark グループ日報システム

## 解決すること

PM が毎日 Jira から手動で課題を引っ張り出し → フォーマットを整えて → グループに投稿。繰り返し作業で、見落としも多い。

**本システム**：Jira 取得 → カスタム条件で絞り込み → カテゴリ別に分類 → Lark グループへ定期配信。完全自動化。

## 主な機能

- 📋 **設定駆動**：`config/settings.json` 一つですべてを制御
- 🔍 **柔軟なフィルタリング**：プロジェクト/担当者/カスタムフィールドの任意の組み合わせ
- 🏷️ **スマート分類**：概要のキーワードで自動分類
- ⏰ **定期配信**：毎日決まった時間に Lark グループへプッシュ
- 🎭 **一言ジョーク**：日報の最後にランダムな一言を添えて
- 🖥️ **クライアント＋サーバー**：社内マシンでデータ取得 → クラウドから配信

## クイックスタート

```bash
pip install requests
cp config/settings.example.json config/settings.json
# settings.json を編集し、Jira と Lark の認証情報を入力
python3 server.py          # サーバー起動
python3 jira_fetcher.py    # Jira から取得
python3 send_daily.py      # テスト配信
```

## 設定

```json
{
  "jira": { "url": "...", "project": "E0V", "auth": {"username":"","password":""} },
  "filter": {
    "statuses": ["已分配","分析中","修复中"],
    "categories": [
      {"name":"ビジュアル", "emoji":"👁️", "match":"exclude", "exclude_keyword":"健康检测"},
      {"name":"ヘルスチェック", "keyword":"健康检测", "emoji":"💊", "match":"include"}
    ]
  },
  "feishu": { "app_id":"", "app_secret":"", "chat_id":"", "chat_type":"group" },
  "schedule": { "fetch_times": ["10:30","15:30"], "report_times": ["11:00","16:00"] }
}
```

## 技術スタック

Python 3.9+ · 設定駆動 · Lark Open API · Jira REST API
