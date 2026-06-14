from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import AgentConfigError, AgentExecutionError
from app.llm.openai_compatible import OpenAICompatibleClient, extract_message
from app.mcp.client import MCPToolClient
from app.schemas import AgentTraceStep, ChatRequest, ChatResponse, IncidentRecord, PendingAction, ToolCallRecord
from app.storage.history import IncidentStore
from app.tools.base import ToolContext


MAX_HISTORY_MESSAGES = 60
SENSITIVE_ARGUMENT_KEYWORDS = ("key", "token", "secret", "password", "authorization", "credential")


SYSTEM_PROMPT = """你是一个面向 Docker/Web 服务的智能运维诊断 Agent。
你的任务是先收集证据，再给出结论；不要凭空猜测。
你只能通过提供的工具了解系统状态或执行操作。
高风险或会改变状态的操作必须尊重工具返回的 approval_required。
用户可能使用"它""刚才那个容器"等指代，请结合短期对话上下文判断对象。
常用工具选择：需要总览或资源占用时先用 docker_overview；需要查容器列表用 list_containers；需要容器深度信息用 inspect_container/process_container/get_container_logs；需要容器生命周期用 start_container/stop_container/restart_container/pause_container/unpause_container/delete_container；需要交互式创建容器对应 create_container；需要管理镜像用 list_images/pull_image/tag_image/untag_image/import_image/export_image/remove_image/prune_images；需要管理网络和卷用 list_networks/inspect_network/create_network/remove_network/prune_networks/connect_network/disconnect_network/list_volumes/inspect_volume/create_volume/remove_volume/prune_volumes；需要管理 Compose 用 list_compose_projects/read_compose_file/write_compose_file/create_compose_project/create_compose_project_from_url/create_compose_project_from_git/compose_*，按 service 操作用 compose_service_*，按 service 看日志用 get_compose_service_logs。
如果工具列表里出现“服务名__工具名”格式的工具，它来自用户配置的外部 MCP。需要阅读网页教程、远程文档或第三方资料时，优先调用合适的外部 MCP 工具获取资料，再结合内置 Docker/Compose 工具执行部署。
回答需要包含：已检查项、主要发现、建议下一步。保持简洁、可执行。
"""


class AgentService:
    def __init__(self, settings: Settings, mcp_client: MCPToolClient, store: IncidentStore) -> None:
        self.settings = settings
        self.mcp_client = mcp_client
        self.store = store

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        final_response: ChatResponse | None = None
        async for event in self.stream_chat(request):
            if event.get("type") == "final":
                final_response = ChatResponse.model_validate(event["response"])
        if final_response is None:
            raise AgentExecutionError("LLM Agent 没有返回最终响应。")
        return final_response

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        session_id = request.session_id or uuid4().hex
        incident_id = uuid4().hex
        created_at = datetime.now().astimezone()
        # 工具上下文只携带本次请求的用户意图，不做全局持久化。
        ctx = ToolContext(approve_actions=request.approve_actions, dry_run=request.dry_run)

        if not self.settings.llm_enabled:
            raise AgentConfigError("LLM API 未配置。请在 .env 中设置 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL。")

        try:
            async for event in self._run_llm_agent_events(request, ctx):
                if event.get("type") != "final_payload":
                    yield event
                    continue
                answer = str(event["answer"])
                tool_calls = event["tool_calls"]
                agent_trace = event["agent_trace"]
        except BaseExceptionGroup as exc:
            raise AgentExecutionError(f"LLM Agent 执行失败：{describe_exception(exc)}") from exc
        except Exception as exc:  # noqa: BLE001 - keep API error shape stable.
            raise AgentExecutionError(f"LLM Agent 执行失败：{describe_exception(exc)}") from exc

        pending_actions = [
            PendingAction(tool_name=call.tool_name, arguments=call.arguments, reason=call.summary)
            for call in tool_calls
            if call.status == "approval_required"
        ]
        response = ChatResponse(
            incident_id=incident_id,
            session_id=session_id,
            answer=answer,
            tool_calls=tool_calls,
            agent_trace=agent_trace,
            pending_actions=pending_actions,
            used_llm=True,
            created_at=created_at,
        )
        self.store.save(IncidentRecord(user_message=request.message, **response.model_dump()))
        yield {"type": "final", "response": response.model_dump(mode="json")}

    async def _run_llm_agent(self, request: ChatRequest, ctx: ToolContext) -> tuple[str, list[ToolCallRecord], list[AgentTraceStep]]:
        async for event in self._run_llm_agent_events(request, ctx):
            if event.get("type") == "final_payload":
                return event["answer"], event["tool_calls"], event["agent_trace"]
        raise AgentExecutionError("LLM Agent 没有返回最终响应。")

    async def _run_llm_agent_events(self, request: ChatRequest, ctx: ToolContext) -> AsyncIterator[dict[str, Any]]:
        client = OpenAICompatibleClient(self.settings)
        tool_calls: list[ToolCallRecord] = []
        agent_trace: list[AgentTraceStep] = [
            AgentTraceStep(
                type="analysis",
                title="分析请求",
                summary="已整理本轮用户问题、短期对话上下文和可用工具，准备让模型判断是否需要调用工具。",
            )
        ]
        history_hint = self._build_history_hint(request.message)
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": history_hint} if history_hint else {"role": "system", "content": "暂无可用历史事件。"},
        ]
        messages.extend(self._build_conversation_messages(request))
        messages.append({"role": "user", "content": request.message})

        # 从 MCP client 获取可用工具。
        tools = await self.mcp_client.list_openai_tools()

        # 在整个 Agent 工具循环期间保持同一个 MCP 会话。
        async with self.mcp_client.session(ctx) as mcp_session:
            for _ in range(request.max_tool_rounds):
                response = await client.chat(messages, tools=tools)
                assistant_message = extract_message(response)
                messages.append(assistant_message)
                raw_tool_calls = assistant_message.get("tool_calls") or []
                if not raw_tool_calls:
                    answer = assistant_message.get("content") or self._summarize_tool_results(tool_calls)
                    agent_trace.append(AgentTraceStep(type="summary", title="生成结论", summary=_compact_text(answer)))
                    yield {"type": "final_payload", "answer": answer, "tool_calls": tool_calls, "agent_trace": agent_trace}
                    return

                for raw_call in raw_tool_calls:
                    function = raw_call.get("function") or {}
                    name = function.get("name") or ""
                    arguments = self._parse_tool_arguments(function.get("arguments"))
                    safe_arguments = sanitize_trace_arguments(arguments)
                    yield {
                        "type": "tool_call_start",
                        "tool_name": name,
                        "arguments": safe_arguments,
                    }

                    # 通过 MCP 执行工具，把审批和 dry-run 策略放在模型之外强制执行。
                    record = await self.mcp_client.execute_tool(mcp_session, name, arguments, ctx)
                    record.arguments = safe_arguments
                    tool_calls.append(record)
                    agent_trace.append(
                        AgentTraceStep(
                            type="tool_call",
                            title=f"调用工具 {name}",
                            summary=record.summary or "工具已返回结果。",
                            tool_name=name,
                            arguments=safe_arguments,
                            status=record.status,
                        )
                    )
                    yield {
                        "type": "tool_call_done",
                        "tool_name": name,
                        "status": record.status,
                        "summary": record.summary,
                    }

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": raw_call.get("id"),
                            "name": name,
                            "content": json.dumps(record.model_dump(mode="json"), ensure_ascii=False),
                        }
                    )

        messages.append(
            {
                "role": "user",
                # 如果模型耗尽工具轮次，强制它基于已收集证据给出最终回答。
                "content": "请基于已经执行的工具结果给出最终诊断结论，不要继续调用工具。",
            }
        )
        response = await client.chat(messages, tools=None)
        final_message = extract_message(response)
        answer = final_message.get("content") or self._summarize_tool_results(tool_calls)
        agent_trace.append(AgentTraceStep(type="summary", title="生成结论", summary=_compact_text(answer)))
        yield {"type": "final_payload", "answer": answer, "tool_calls": tool_calls, "agent_trace": agent_trace}

    def _build_history_hint(self, message: str) -> str:
        similar = self.store.similar_by_message(message, limit=3)
        if not similar:
            return ""
        items = []
        for record in similar:
            items.append(
                {
                    "incident_id": record.incident_id,
                    "user_message": record.user_message,
                    "answer": record.answer[:500],
                    "created_at": record.created_at.isoformat(),
                }
            )
        return "以下是相似历史事件，可作为参考，不可当作当前事实：\n" + json.dumps(items, ensure_ascii=False)

    @staticmethod
    def _build_conversation_messages(request: ChatRequest) -> list[dict]:
        messages = []
        for item in request.history[-MAX_HISTORY_MESSAGES:]:
            content = item.content.strip()
            if content:
                # 限制每条历史消息长度，避免历史过长导致 LLM 请求失控。
                messages.append({"role": item.role, "content": content[-4000:]})
        return messages

    @staticmethod
    def _parse_tool_arguments(raw: object) -> dict:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        if isinstance(raw, str):
            try:
                value = json.loads(raw)
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _summarize_tool_results(tool_calls: list[ToolCallRecord]) -> str:
        if not tool_calls:
            return "未调用工具，无法形成诊断结论。"
        lines = ["已完成工具检查，结果如下："]
        for call in tool_calls:
            lines.append(f"- {call.tool_name}: {call.summary}")
        return "\n".join(lines)


def describe_exception(exc: BaseException) -> str:
    """返回叶子异常信息，避免 TaskGroup 包装隐藏根因。"""
    leaf_messages = _collect_leaf_exception_messages(exc)
    if leaf_messages:
        return "；".join(dict.fromkeys(leaf_messages))
    return str(exc)


def sanitize_trace_arguments(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[str(key)] = "***"
            else:
                sanitized[str(key)] = sanitize_trace_arguments(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_trace_arguments(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(keyword in normalized for keyword in SENSITIVE_ARGUMENT_KEYWORDS)


def _compact_text(text: str, limit: int = 180) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _collect_leaf_exception_messages(exc: BaseException) -> list[str]:
    nested = getattr(exc, "exceptions", None)
    if nested:
        messages: list[str] = []
        for item in nested:
            if isinstance(item, BaseException):
                messages.extend(_collect_leaf_exception_messages(item))
        return messages
    message = str(exc).strip()
    return [message or type(exc).__name__]
