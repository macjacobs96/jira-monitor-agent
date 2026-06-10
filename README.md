<p align="center">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README_EN.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_JA.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
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
- ⏰ **定时推送**：每天 10:30 / 15:30 自动推送飞书群
- 🧠 **AI 根因分析**（可选）：DeepSeek 自动分析 + PRD 范围判定 + 飞书云文档
- 🔗 **frp 隧道**：服务器通过 Mac 内网隧道直连公司 Jira

## 架构

```
Mac（公司内网）              服务器 43.159.43.36
┌──────────────┐            ┌─────────────────────────────┐
│ frpc tunnel  │───7000──→  │ frps ← cron 10:30 / 15:30   │
│     ↕        │            │   ↓                          │
│  Jira 内网   │            │ jira_fetcher_server.py       │
│              │            │   ↓                          │
│  （仅做隧道） │            │ send_simple_report.py        │
│              │            │   ↓                          │
│              │            │ 飞书群推送                   │
└──────────────┘            └─────────────────────────────┘
```

## 快速开始

```bash
pip install requests
```

### 1. Mac 端启动隧道

```bash
cd frpc_mac && nohup ./frpc -c frpc.toml > /tmp/frpc.log 2>&1 &
```

### 2. 服务器端手动采集 + 推送

```bash
# 采集数据
python3 jira_fetcher_server.py --no-analyze

# 推送精简日报
python3 send_simple_report.py
```

### 3. AI 分析（可选）

```bash
# 采集 + AI 根因分析 + 飞书云文档
python3 jira_fetcher_server.py
```

## 项目结构

```
├── jira_fetcher_server.py   # 服务器端采集脚本（frp 代理访问 Jira）
├── send_simple_report.py    # 精简日报生成+推送
├── server.py                # HTTP 服务（手动触发/兼容旧接口）
├── ai_analyzer.py           # AI 根因分析引擎（DeepSeek）
├── prd_scope.py             # PRD 范围判定
├── dual_report.py           # 双输出：文本+飞书云文档
├── src/
│   └── analyzer.py          # 数据分析引擎（筛选/分组/格式化）
├── config/
│   └── settings.example.json
├── data/                    # 数据快照
├── memory/                  # AI 记忆库
├── prd/                     # PRD 文档
├── frpc.toml                # Mac frpc 隧道配置
└── README.md
```

## 定时调度

| 时间 | 操作 |
|------|------|
| 10:30 | 采集 Jira 数据 |
| 10:30 | 飞书群推送精简日报 |
| 15:30 | 采集 Jira 数据 |
| 15:30 | 飞书群推送精简日报 |

通过 OpenClaw cron 管理，工作日（周一～周五）自动执行。

## 技术栈

Python 3.9+ · 配置驱动 · 飞书 Open API · Jira REST API · frp 内网穿透 · DeepSeek AI · OpenClaw Cron
