<p align="center">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README_EN.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_JA.md">🇯🇵 日本語</a>
</p>

---

# Jira Monitor Agent

> 配置驱动的 Jira 问题监控 + 飞书群定时日报系统

## 解决什么问题？

项目经理每天要从 Jira 翻出一堆 Case → 手动整理格式 → 发群里。重复劳动，容易漏。

**本系统**：拉 Jira → 按自定义条件筛选 → 按类别分组 → 飞书群定时推送，全程自动。

## 核心特性

- 📋 **配置驱动**：一个 `config/settings.json` 控制所有行为
- 🔍 **灵活筛选**：项目/经办人/自定义字段任意组合
- 🏷️ **智能分类**：按关键字自动归类（如视觉/健康检测）
- ⏰ **定时推送**：每天固定时间推飞书群
- 🎭 **吉祥话**：日报末尾随机附赠阴阳怪气
- 🖥️ **客户端+服务端**：内网机器拉数据 → 云端推送

## 快速开始

```bash
pip install requests
```

### 1. 修改配置

```bash
cp config/settings.example.json config/settings.json
# 编辑 settings.json，填入 Jira 地址、账号、飞书凭证
```

### 2. 启动服务端

```bash
python3 server.py
```

### 3. 拉取数据（客户端）

```bash
# 正常采集
python3 jira_fetcher.py

# 诊断模式（确认字段名）
python3 jira_fetcher.py --diag
```

### 4. 测试推送

```bash
python3 send_daily.py
```

## 配置说明

```json
{
  "jira": {
    "url": "Jira 地址",
    "project": "项目 Key",
    "auth": { "username": "账号", "password": "密码" },
    "jql_filters": {
      "assignee": "经办人",
      "custom_fields": [
        { "name": "控制器(单选)", "value": "ICC-视觉" }
      ]
    }
  },
  "filter": {
    "statuses": ["已分配", "分析中", "修复中"],
    "categories": [
      { "name": "视觉", "emoji": "👁️", "match": "exclude", "exclude_keyword": "健康检测" },
      { "name": "健康检测", "keyword": "健康检测", "emoji": "💊", "match": "include" }
    ]
  },
  "feishu": {
    "app_id": "飞书应用 ID",
    "app_secret": "飞书应用密钥",
    "chat_id": "群 chat_id 或用户 open_id",
    "chat_type": "group"
  },
  "schedule": {
    "fetch_times": ["10:30", "15:30"],
    "report_times": ["11:00", "16:00"]
  }
}
```

### 分类规则

| match 类型 | 说明 | 示例 |
|-----------|------|------|
| `include` | 含 keyword 归入此类 | `"keyword": "健康检测"` |
| `exclude` | 不含 exclude_keyword 归入此类 | `"exclude_keyword": "健康检测"` |

## 项目结构

```
├── server.py             # 服务端（接收 + 推送）
├── jira_fetcher.py       # 客户端（拉 Jira 数据）
├── send_daily.py         # 手动触发日报
├── config/
│   └── settings.json     # 配置文件
├── src/
│   └── analyzer.py       # 数据分析引擎
├── data/                 # 数据快照
└── README.md
```

## 部署建议

- **客户端**：放在能访问 Jira 的电脑上，crontab 定时跑
- **服务端**：有公网 IP 的服务器，PM2 守护
- **飞书**：创建独立机器人，只推送不打扰

## 技术栈

Python 3.9+ · 配置驱动 · 飞书 Open API · Jira REST API
