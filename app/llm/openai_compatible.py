from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


LLM_HTTP_TIMEOUT = httpx.Timeout(connect=20.0, read=180.0, write=30.0, pool=20.0)
LLM_READ_TIMEOUT_RETRIES = 1


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.llm_base_url.rstrip("/")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=LLM_HTTP_TIMEOUT) as client:
            for attempt in range(LLM_READ_TIMEOUT_RETRIES + 1):
                try:
                    response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                    return parse_llm_json_response(response)
                except httpx.ReadTimeout as exc:
                    # 读超时只重试一次，缓解临时网关卡顿，同时不掩盖持续性问题。
                    if attempt >= LLM_READ_TIMEOUT_RETRIES:
                        raise RuntimeError(format_llm_timeout_error(self.settings.llm_model, LLM_HTTP_TIMEOUT.read)) from exc

        raise RuntimeError(format_llm_timeout_error(self.settings.llm_model, LLM_HTTP_TIMEOUT.read))


def format_llm_timeout_error(model: str, timeout_seconds: float | None) -> str:
    timeout_text = f"{timeout_seconds:g} 秒" if timeout_seconds is not None else "配置时间"
    return f"LLM API 响应超时：模型 {model or 'unknown'} 在 {timeout_text} 内没有返回，请稍后重试或检查代理网关。"


def parse_llm_json_response(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        # 代理配置错误时常返回 HTML，这里保留一小段响应便于诊断。
        preview = " ".join(response.text.strip().split())[:200]
        raise RuntimeError(
            "LLM API 返回了非 JSON 响应。"
            "请检查 LLM_BASE_URL 是否指向 OpenAI 兼容接口根路径，例如需要包含 /v1。"
            f"content-type={content_type or 'unknown'}"
            + (f"，响应片段={preview}" if preview else "")
        )
    try:
        value = response.json()
    except ValueError as exc:
        raise RuntimeError("LLM API 返回内容不是合法 JSON，请检查代理网关或模型服务返回。") from exc
    if not isinstance(value, dict):
        raise RuntimeError("LLM API 返回 JSON 顶层不是对象。")
    return value


def extract_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices:
        return {"role": "assistant", "content": ""}
    return choices[0].get("message") or {"role": "assistant", "content": ""}
