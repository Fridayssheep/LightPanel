"""诊断报告生成服务，按需生成结构化报告。"""
from __future__ import annotations

import json
from datetime import datetime

from app.config import Settings
from app.errors import AgentConfigError, AgentExecutionError
from app.llm.openai_compatible import OpenAICompatibleClient, extract_message
from app.schemas import DiagnosisReport, IncidentRecord


# 复用 AgentService 的异常展开逻辑，避免 TaskGroup 包装隐藏真实原因。
def describe_exception(exc: BaseException) -> str:
    """返回叶子异常信息，避免 TaskGroup 包装隐藏根因。"""
    from app.agent.service import describe_exception as _describe
    return _describe(exc)


REPORT_SYSTEM_PROMPT = """你是一个运维故障报告生成助手。
你会收到一次运维诊断的完整记录：用户问题、Agent 调用的工具及结果、Agent 最终回答。
请把它整理成一份结构化的故障诊断报告。

必须调用 emit_report 函数返回结果，字段要求：
- title: 一句话故障标题
- symptom: 故障现象描述
- checked_items: 已检查项列表（基于实际调用的工具）
- findings: 主要发现列表
- root_cause: 根因分析，如果证据不足就说明无法确定
- recommendations: 处理建议列表，可执行
- final_status: 最终状态，比如"已恢复""待处理""需人工介入"
- severity: 严重程度，从 info/low/medium/high 中选

不要编造没有发生的检查或证据，只基于提供的记录。
"""


REPORT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "emit_report",
        "description": "输出结构化的故障诊断报告。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "一句话故障标题。"},
                "symptom": {"type": "string", "description": "故障现象描述。"},
                "checked_items": {"type": "array", "items": {"type": "string"}, "description": "已检查项。"},
                "findings": {"type": "array", "items": {"type": "string"}, "description": "主要发现。"},
                "root_cause": {"type": "string", "description": "根因分析。"},
                "recommendations": {"type": "array", "items": {"type": "string"}, "description": "处理建议。"},
                "final_status": {"type": "string", "description": "最终状态。"},
                "severity": {"type": "string", "enum": ["info", "low", "medium", "high"], "description": "严重程度。"},
            },
            "required": ["title", "symptom", "checked_items", "findings", "root_cause", "recommendations", "final_status", "severity"],
        },
    },
}


class ReportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, incident: IncidentRecord) -> DiagnosisReport:
        if not self.settings.llm_enabled:
            raise AgentConfigError("LLM API 未配置，无法生成诊断报告。")

        client = OpenAICompatibleClient(self.settings)
        context = self._build_context(incident)
        messages = [
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            # 强制模型走函数输出，让报告弹窗拿到稳定的结构化字段。
            response = await client.chat(
                messages,
                tools=[REPORT_TOOL_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "emit_report"}},
            )
        except Exception as exc:  # noqa: BLE001
            raise AgentExecutionError(f"报告生成失败：{describe_exception(exc)}") from exc

        payload = self._extract_report_payload(response)
        return DiagnosisReport(
            incident_id=incident.incident_id,
            title=payload.get("title", "未命名故障"),
            symptom=payload.get("symptom", incident.user_message),
            checked_items=payload.get("checked_items", []),
            findings=payload.get("findings", []),
            root_cause=payload.get("root_cause", ""),
            recommendations=payload.get("recommendations", []),
            final_status=payload.get("final_status", ""),
            severity=payload.get("severity", "info"),
            generated_at=datetime.now().astimezone(),
        )

    @staticmethod
    def _build_context(incident: IncidentRecord) -> str:
        tool_lines = []
        for call in incident.tool_calls:
            # 带上原始工具数据，确保报告基于证据而不是只复述结论。
            tool_lines.append(
                {
                    "tool": call.tool_name,
                    "arguments": call.arguments,
                    "status": call.status,
                    "summary": call.summary,
                    "data": call.data,
                }
            )
        payload = {
            "user_message": incident.user_message,
            "agent_answer": incident.answer,
            "tool_calls": tool_lines,
            "created_at": incident.created_at.isoformat(),
        }
        return "以下是本次运维诊断的完整记录：\n" + json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _extract_report_payload(response: dict) -> dict:
        message = extract_message(response)
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            function = tool_calls[0].get("function") or {}
            raw_args = function.get("arguments")
            if isinstance(raw_args, str):
                try:
                    return json.loads(raw_args)
                except json.JSONDecodeError:
                    return {}
            if isinstance(raw_args, dict):
                return raw_args
        # 部分 OpenAI-compatible 网关会忽略 tool_choice；这里兼容直接返回 JSON 文本。
        content = message.get("content") or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
