"""
PRD 范围分析引擎
- 从 PRD 文档提取功能清单
- 对 Jira Case 进行范围判定：在PRD内/外/模糊
"""
import json, os, requests

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = "sk-d507c4ac5b464286b2b975b7629d13d4"

PRD_DIR = "/root/jira_agent/prd"
DATA_DIR = "/root/jira_agent/data"
os.makedirs(PRD_DIR, exist_ok=True)

# ── PRD 功能清单 ───────────────────────────────────────

E0V_SCOPE = """
## 智慧识别（DMS/OMS/RMS）- 视觉
### 人脸识别
- 人脸录入：用户注册人脸信息
- 人脸绑定：将人脸与账户绑定
- 人脸解绑：解绑人脸与账户
- 人脸登录：通过人脸识别登录账户
- 人脸识别准确率：拒识率/误识率
- 多用户人脸管理：家庭成员/多账户切换
- 人脸数据安全/隐私保护

### DMS 驾驶员监测
- 疲劳驾驶检测：打哈欠/闭眼/低头
- 分心驾驶检测：长时间视线偏离
- 吸烟检测
- 打电话检测
- 驾驶员身份识别
- 驾驶员注意力监测

### OMS 乘员监测
- 乘员数量/位置检测
- 儿童检测/遗留提醒（CPD）
- 安全带检测
- 物品遗留检测
- 宠物检测

### 手势/表情识别
- 手势控制（音量/切歌/接听等）
- 表情识别
- 视线追踪

## 健康检测（Health）
### 健康监测
- 静态心率检测（bpm）
- 呼吸频率检测
- 血氧饱和度（SpO2）
- 心率变异性（HRV）
- 血压检测
- 体温检测
- 快速检测模式
- 无感/持续检测

### 健康报告
- 健康档案：历史数据查看
- 健康报告生成
- 健康评分/评估
- 异常指标提醒
- 趋势分析

### 健康Agent
- AI健康解读
- 用药提醒/建议
- 健康问答
- 就医建议

## 账户/个人中心
- 账号登录（人脸/验证码/密码）
- 账号绑定/解绑
- 个人中心设置
- 用户偏好/记忆
- 家庭成员管理
- 数据同步（云端/本地）

## 仪表/中控交互
- 仪表状态指示（人脸绑定状态/DMS状态等）
- 中控-仪表文言同步
- 多屏交互
- HMI适配

## 系统/OTA
- OTA升级
- 系统设置（语言/单位等）
- 权限管理
- 日志/诊断
"""

# ── 范围判定 Prompt ────────────────────────────────────

SCOPE_PROMPT = """你是奇瑞E0V项目的需求分析专家。根据以下PRD功能清单，判定Jira Case是否在PRD范围内。

## E0V PRD 功能范围
{scope}

## Jira Case
Key: {key}
标题: {summary}
描述: {desc}

## 判定规则
- "in_scope": Case描述的功能/问题，PRD中明确提及
- "out_of_scope": PRD中未提及的功能/模块/问题，不属于我方交付范围
- "borderline": 难以界定，可能部分相关

## 输出（仅JSON）
```json
{{
  "scope": "in_scope / out_of_scope / borderline",
  "reason": "判定依据（<50字）",
  "relevant_prd_section": "PRD中对应章节"
}}
```"""


def call_llm(messages, max_tokens=500):
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.1, "max_tokens": max_tokens},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def check_scope(key, summary, description=""):
    """判定单个 Case 是否在 PRD 范围内"""
    prompt = SCOPE_PROMPT.format(scope=E0V_SCOPE[:3000], key=key, summary=summary[:200], desc=(description or "")[:300])
    try:
        result = call_llm([{"role": "user", "content": prompt}], max_tokens=300)
        import re
        m = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return json.loads(result)
    except:
        return {"scope": "borderline", "reason": "AI判定失败", "relevant_prd_section": ""}


def batch_check_scope(issues):
    """批量范围判定"""
    results = []
    for issue in issues:
        key = issue.get("key", "?")
        summary = issue.get("fields", {}).get("summary", "")
        desc = issue.get("_description", issue.get("fields", {}).get("description", "")) or ""
        scope = check_scope(key, summary, desc)
        scope["_key"] = key
        results.append(scope)
    return results


def scope_summary(results):
    """汇总范围判定"""
    in_scope = [r for r in results if r.get("scope") == "in_scope"]
    out_scope = [r for r in results if r.get("scope") == "out_of_scope"]
    borderline = [r for r in results if r.get("scope") == "borderline"]
    return {
        "total": len(results),
        "in_scope": len(in_scope),
        "out_of_scope": len(out_scope),
        "borderline": len(borderline),
        "in_scope_list": [r["_key"] for r in in_scope],
        "out_of_scope_list": [r["_key"] for r in out_scope],
        "borderline_list": [r["_key"] for r in borderline],
    }


# ── 集成到分析流程 ─────────────────────────────────────

def enrich_analysis_with_scope(analysis_result):
    """为已有分析结果添加 PRD 范围判定"""
    analyses = analysis_result.get("analyses", [])
    if not analyses:
        return analysis_result

    issues_for_scope = []
    for a in analyses:
        issues_for_scope.append({
            "key": a.get("_key", "?"),
            "fields": {
                "summary": a.get("_summary", ""),
            },
            "_description": "",
        })

    print(f"🔍 PRD范围判定 {len(issues_for_scope)} 条...")
    scope_results = batch_check_scope(issues_for_scope)

    # 合并
    for a, s in zip(analyses, scope_results):
        a["scope"] = s.get("scope", "borderline")
        a["scope_reason"] = s.get("reason", "")
        a["scope_prd_section"] = s.get("relevant_prd_section", "")

    analysis_result["scope_summary"] = scope_summary(scope_results)
    return analysis_result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/root/jira_agent")
    # 加载最新分析结果
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("analysis_") and f.endswith(".json")], reverse=True)
    if files:
        with open(os.path.join(DATA_DIR, files[0])) as f:
            result = json.load(f)
        result = enrich_analysis_with_scope(result)
        print(json.dumps(result.get("scope_summary", {}), ensure_ascii=False, indent=2))
        # 保存
        with open(os.path.join(DATA_DIR, files[0]), "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
