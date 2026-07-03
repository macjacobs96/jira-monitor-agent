import re

with open("/root/jira_agent/send_simple_report.py", "r") as f:
    content = f.read()

# Change 1: Expand status filter
content = content.replace(
    'TARGET_STATUSES = {"已分配", "分析中", "修复中"}',
    'ACTIVE_STATUSES = {"已分配", "分析中", "修复中", "验收中", "处理中", "挂起", "申请挂起中"}'
)

# Add CLOSED_STATUSES after ACTIVE_STATUSES
content = content.replace(
    'PRIO_EMOJI',
    'CLOSED_STATUSES = {"完成", "已关闭", "已解决"}\nPRIO_EMOJI'
)

# Change 2: Replace TARGET_STATUSES reference with ACTIVE_STATUSES
content = content.replace('TARGET_STATUSES', 'ACTIVE_STATUSES')

# Change 3: Add health_extra merge logic after the filter loop
old_block = "        active.append(i)\n\n    if not active:"
new_block = """        active.append(i)

    # 健康检测 — 额外拉入全部控制器的活跃问题
    health_extra = []
    seen_keys = {i["key"] for i in active}
    for i in issues:
        if i["key"] in seen_keys:
            continue
        summary = i.get("fields", {}).get("summary", "")
        if "健康检测" not in summary:
            continue
        status = i.get("fields", {}).get("status", {}).get("name", "")
        if status in CLOSED_STATUSES:
            continue
        health_extra.append(i)

    active.extend(health_extra)

    if not active:"""

content = content.replace(old_block, new_block)

with open("/root/jira_agent/send_simple_report.py", "w") as f:
    f.write(content)

print("Patch applied successfully")
