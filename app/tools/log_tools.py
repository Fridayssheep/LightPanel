from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import get_settings
from app.tools.base import ToolContext, error, success


def _is_allowed_path(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def read_log_tail(path: str, lines: int = 120, ctx: ToolContext | None = None) -> dict[str, Any]:
    settings = get_settings()
    target = Path(path)
    if not target.is_absolute():
        target = Path.cwd() / target
    if not _is_allowed_path(target, settings.parsed_log_roots):
        return error(
            "日志路径不在允许读取范围内。",
            path=str(target),
            allowed_roots=[str(root) for root in settings.parsed_log_roots],
        )
    if not target.exists() or not target.is_file():
        return error("日志文件不存在。", path=str(target))
    safe_lines = max(1, min(lines, 1000))
    with target.open("r", encoding="utf-8", errors="replace") as file:
        content_lines = file.readlines()[-safe_lines:]
    content = "".join(content_lines)
    return success(
        f"已读取日志尾部 {len(content_lines)} 行。",
        path=str(target),
        lines=len(content_lines),
        content=content[-12000:],
        quick_findings=_detect_log_findings(content),
    )


def analyze_log_text(log_text: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    text = log_text[-12000:]
    return success("已完成日志规则分析。", findings=_detect_log_findings(text), sample=text[-2000:])


def _detect_log_findings(content: str) -> list[dict[str, str]]:
    lower = content.lower()
    findings: list[dict[str, str]] = []
    checks = [
        ("port_conflict", ["address already in use", "bind() to", "端口", "占用"], "疑似端口冲突或监听失败。"),
        ("permission", ["permission denied", "access denied", "权限"], "疑似权限不足。"),
        ("database", ["connection refused", "database", "mysql", "postgres", "redis"], "疑似依赖服务或数据库连接异常。"),
        ("not_found", ["no such file", "not found", "不存在"], "疑似文件路径或资源不存在。"),
        ("timeout", ["timeout", "timed out", "超时"], "疑似网络或依赖调用超时。"),
        ("nginx_config", ["nginx", "emerg", "directive", "configuration file"], "疑似 Nginx 配置错误。"),
        ("http_5xx", [" 500 ", " 502 ", " 503 ", " 504 "], "出现 HTTP 5xx 服务端错误。"),
    ]
    for code, needles, message in checks:
        if any(needle in lower for needle in needles):
            findings.append({"code": code, "message": message})
    if not findings and content.strip():
        findings.append({"code": "no_obvious_pattern", "message": "未命中明显错误模式，需要结合上下文继续判断。"})
    if not content.strip():
        findings.append({"code": "empty_log", "message": "日志内容为空。"})
    return findings
