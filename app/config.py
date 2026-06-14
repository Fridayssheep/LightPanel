from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_path_list(value: str) -> list[Path]:
    # 设置界面中的路径列表允许用逗号或换行分隔。
    return [Path(item.strip()).resolve() for item in re.split(r"[\n,]+", value) if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ops Agent"
    data_dir: Path = Field(default=Path("data"), alias="OPS_AGENT_DATA_DIR")
    history_file: Path = Field(default=Path("data/incidents.json"), alias="OPS_AGENT_HISTORY_FILE")
    runtime_settings_file: Path = Field(
        default=Path("data/settings.json"),
        alias="OPS_AGENT_RUNTIME_SETTINGS_FILE",
    )
    log_roots: str = Field(default="samples/logs", alias="OPS_AGENT_LOG_ROOTS")
    project_roots: str = Field(default="samples", alias="OPS_AGENT_PROJECT_ROOTS")

    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")

    docker_http_proxy: str = Field(default="", alias="OPS_AGENT_DOCKER_HTTP_PROXY")
    docker_https_proxy: str = Field(default="", alias="OPS_AGENT_DOCKER_HTTPS_PROXY")
    docker_no_proxy: str = Field(default="", alias="OPS_AGENT_DOCKER_NO_PROXY")
    external_mcp_servers: str = Field(default="", alias="OPS_AGENT_EXTERNAL_MCP_SERVERS")
    enable_public_mcp: bool = Field(default=False, alias="OPS_AGENT_ENABLE_PUBLIC_MCP")

    require_dangerous_approval: bool = Field(default=True, alias="OPS_AGENT_REQUIRE_DANGEROUS_APPROVAL")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def parsed_log_roots(self) -> list[Path]:
        return [Path(item.strip()).resolve() for item in self.log_roots.split(",") if item.strip()]

    @property
    def parsed_project_roots(self) -> list[Path]:
        return _parse_path_list(self.project_roots)

@lru_cache
def get_settings() -> Settings:
    # 服务端和 MCP 共享同一个 Settings 实例，运行时 JSON 在启动时应用一次。
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.history_file.parent.mkdir(parents=True, exist_ok=True)
    settings.runtime_settings_file.parent.mkdir(parents=True, exist_ok=True)
    apply_runtime_settings_file(settings)
    return settings


RUNTIME_SETTING_KEYS = {
    "log_roots",
    "project_roots",
    "require_dangerous_approval",
    "llm_base_url",
    "llm_api_key",
    "llm_model",
    "docker_http_proxy",
    "docker_https_proxy",
    "docker_no_proxy",
    "external_mcp_servers",
    "enable_public_mcp",
}


def apply_runtime_settings_file(settings: Settings) -> None:
    # 运行时设置只允许白名单字段覆盖环境变量值。
    runtime_file = Path(settings.runtime_settings_file)
    if not runtime_file.is_file():
        return

    try:
        payload = json.loads(runtime_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict):
        return

    for key in RUNTIME_SETTING_KEYS:
        if key in payload:
            setattr(settings, key, payload[key])


def save_runtime_settings_file(settings: Settings) -> None:
    runtime_file = Path(settings.runtime_settings_file)
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    # 接口密钥在界面侧按只写处理：空值表示保留当前值。
    payload: dict[str, Any] = {
        "log_roots": settings.log_roots,
        "project_roots": settings.project_roots,
        "require_dangerous_approval": settings.require_dangerous_approval,
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "docker_http_proxy": getattr(settings, "docker_http_proxy", ""),
        "docker_https_proxy": getattr(settings, "docker_https_proxy", ""),
        "docker_no_proxy": getattr(settings, "docker_no_proxy", ""),
        "external_mcp_servers": getattr(settings, "external_mcp_servers", ""),
        "enable_public_mcp": getattr(settings, "enable_public_mcp", False),
    }
    if settings.llm_api_key:
        payload["llm_api_key"] = settings.llm_api_key
    runtime_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
