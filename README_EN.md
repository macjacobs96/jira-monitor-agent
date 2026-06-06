<p align="center">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README_EN.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_JA.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README_AR.md">🇸🇦 العربية</a>
</p>

---

# Jira Monitor Agent

> Config-driven Jira issue monitoring + scheduled Feishu group daily report

## What It Does

PMs manually pull Jira cases → format → post to group chat. Repetitive, error-prone.

**This tool**: Fetch Jira → filter by custom rules → categorize → push to Feishu group on schedule. Fully automated.

## Key Features

- 📋 **Config-driven**: One `settings.json` controls everything
- 🔍 **Flexible filtering**: Project / assignee / custom fields any combo
- 🏷️ **Smart categorization**: Auto-group by keywords in summary
- ⏰ **Scheduled push**: Fixed daily times to Feishu group
- 🎭 **Quips**: Random sassy remarks at the bottom
- 🖥️ **Client + Server**: LAN machine fetches → cloud server delivers

## Quick Start

```bash
pip install requests
cp config/settings.example.json config/settings.json
# Edit settings.json with your Jira + Feishu credentials
python3 server.py          # Start server
python3 jira_fetcher.py    # Fetch from Jira
python3 send_daily.py      # Test push
```

## Config

```json
{
  "jira": { "url": "...", "project": "E0V", "auth": {"username":"","password":""} },
  "filter": {
    "statuses": ["已分配","分析中","修复中"],
    "categories": [
      {"name":"Visual", "emoji":"👁️", "match":"exclude", "exclude_keyword":"HealthCheck"},
      {"name":"Health", "keyword":"HealthCheck", "emoji":"💊", "match":"include"}
    ]
  },
  "feishu": { "app_id":"", "app_secret":"", "chat_id":"", "chat_type":"group" },
  "schedule": { "fetch_times": ["10:30","15:30"], "report_times": ["11:00","16:00"] }
}
```

## Tech Stack

Python 3.9+ · Config-driven · Feishu Open API · Jira REST API
