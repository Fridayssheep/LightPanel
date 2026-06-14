from __future__ import annotations

import argparse
import os
import sys
from typing import Any
from uuid import uuid4

import httpx
from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_HISTORY_TURNS = 30


def main() -> None:
    parser = argparse.ArgumentParser(description="Ops Agent command line interface.")
    parser.add_argument("--api-url", default=os.getenv("OPS_AGENT_API_URL", DEFAULT_API_URL))
    parser.add_argument("--approve-actions", action="store_true", help="Allow high-risk actions for this CLI session.")
    parser.add_argument("--dry-run", action="store_true", help="Ask tools to avoid state-changing operations.")
    parser.add_argument("--history-turns", type=int, default=DEFAULT_HISTORY_TURNS, help="Number of recent user/assistant turns to send as context.")
    args = parser.parse_args()

    session = CliSession(
        api_url=args.api_url.rstrip("/"),
        approve_actions=args.approve_actions,
        dry_run=args.dry_run,
        history_turns=max(0, args.history_turns),
    )
    session.run()


class CliSession:
    def __init__(
        self,
        api_url: str,
        approve_actions: bool,
        dry_run: bool,
        history_turns: int = DEFAULT_HISTORY_TURNS,
        console: Console | None = None,
    ) -> None:
        self.api_url = api_url
        self.approve_actions = approve_actions
        self.dry_run = dry_run
        self.history_messages = history_turns * 2
        self.history: list[dict[str, str]] = []
        self.session_id = uuid4().hex
        self.console = console or Console()

    def run(self) -> None:
        self._print_banner()
        self._print_health()

        while True:
            try:
                message = Prompt.ask("\n[bold cyan]ops[/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                return
            if not message:
                continue
            if message in {"/quit", "/exit"}:
                return
            if message == "/help":
                self._print_help()
                continue
            if message == "/health":
                self._print_health()
                continue
            if message == "/tools":
                self._print_tools()
                continue
            if message == "/clear":
                self._clear_context()
                continue
            if message == "/approve on":
                self.approve_actions = True
                self._print_notice("高危操作确认已开启。", style="green")
                continue
            if message == "/approve off":
                self.approve_actions = False
                self._print_notice("高危操作确认已关闭。", style="yellow")
                continue
            if message == "/dry on":
                self.dry_run = True
                self._print_notice("dry-run 已开启。", style="green")
                continue
            if message == "/dry off":
                self.dry_run = False
                self._print_notice("dry-run 已关闭。", style="yellow")
                continue
            self._send_message(message)

    def _send_message(self, message: str) -> None:
        self._print_user_message(message)
        payload = {
            "message": message,
            "session_id": self.session_id,
            "history": self.history[-self.history_messages:] if self.history_messages else [],
            "approve_actions": self.approve_actions,
            "dry_run": self.dry_run,
        }
        try:
            with self.console.status("[bold cyan]Agent 正在排查...[/bold cyan]", spinner="dots"):
                response = httpx.post(f"{self.api_url}/agent/chat", json=payload, timeout=90)
        except httpx.HTTPError as exc:
            self._print_error(f"请求失败：{exc}")
            return
        if response.status_code >= 400:
            self._print_error_response(response)
            return
        data = response.json()
        answer = data.get("answer") or "(empty)"
        self._print_agent_answer(answer)
        self._print_tool_calls(data.get("tool_calls") or [])
        pending = data.get("pending_actions") or []
        if pending:
            self._print_pending_actions(pending)
        self._append_history("user", message)
        self._append_history("assistant", answer)

    def _print_health(self) -> None:
        try:
            with self.console.status("[bold cyan]检查后端状态...[/bold cyan]", spinner="dots"):
                response = httpx.get(f"{self.api_url}/health", timeout=10)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._print_error(f"后端不可用：{exc}")
            return
        data = response.json()
        table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
        table.add_column("key", style="cyan", no_wrap=True)
        table.add_column("value")
        table.add_row("status", str(data.get("status")))
        table.add_row("llm", self._bool_text(data.get("llm_enabled")))
        table.add_row("docker", self._bool_text(data.get("docker_available")))
        table.add_row("api", self.api_url)
        self.console.print(Panel(table, title="Health", border_style="cyan"))

    def _print_banner(self) -> None:
        mode = []
        mode.append("approve:on" if self.approve_actions else "approve:off")
        mode.append("dry-run:on" if self.dry_run else "dry-run:off")
        turns = self.history_messages // 2
        mode.append(f"context:{turns} turns")
        body = Text()
        body.append("Ops Agent CUI\n", style="bold cyan")
        body.append("Docker socket 运维 Agent\n", style="white")
        body.append("输入 /help 查看命令，输入 /quit 退出。", style="dim")
        self.console.print(
            Panel(
                Group(body, Text(" | ".join(mode), style="dim")),
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    def _print_tools(self) -> None:
        try:
            with self.console.status("[bold cyan]读取工具列表...[/bold cyan]", spinner="dots"):
                response = httpx.get(f"{self.api_url}/tools", timeout=10)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._print_error(f"工具列表读取失败：{exc}")
            return
        table = Table(title="Tools", box=box.SIMPLE_HEAVY)
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Mode", no_wrap=True)
        table.add_column("Description")
        for item in response.json():
            marker = "confirm" if item.get("requires_approval") else "auto"
            mode_style = "yellow" if marker == "confirm" else "green"
            table.add_row(str(item.get("name")), f"[{mode_style}]{marker}[/{mode_style}]", str(item.get("description")))
        self.console.print(table)

    def _clear_context(self) -> None:
        self.history.clear()
        self.session_id = uuid4().hex
        self._print_notice("当前对话上下文已清空。", style="green")

    def _append_history(self, role: str, content: str) -> None:
        if self.history_messages == 0:
            return
        content = content.strip()
        if not content:
            return
        self.history.append({"role": role, "content": content[-4000:]})
        if self.history_messages:
            self.history = self.history[-self.history_messages:]

    def _print_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        if not tool_calls:
            return
        table = Table(title="Tool Calls", box=box.SIMPLE)
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Summary")
        for call in tool_calls:
            status = str(call.get("status"))
            style = "green" if status == "success" else "yellow" if status in {"approval_required", "skipped"} else "red"
            table.add_row(str(call.get("tool_name")), f"[{style}]{status}[/{style}]", str(call.get("summary")))
        self.console.print(table)

    def _print_error_response(self, response: httpx.Response) -> None:
        try:
            data = response.json()
        except ValueError:
            self.console.print(Panel(f"HTTP {response.status_code} {response.text[:500]}", title="Error", border_style="red"))
            return
        self.console.print(Panel(f"HTTP {response.status_code} {data.get('detail') or data}", title="Error", border_style="red"))

    def _print_help(self) -> None:
        table = Table(title="Commands", box=box.SIMPLE)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Action")
        rows = [
            ("/health", "查看后端、LLM、Docker 状态"),
            ("/tools", "查看 Agent 可调用工具"),
            ("/clear", "清空当前对话上下文"),
            ("/approve on", "允许本轮会话执行高危操作"),
            ("/approve off", "关闭高危操作确认"),
            ("/dry on", "开启 dry-run"),
            ("/dry off", "关闭 dry-run"),
            ("/quit", "退出"),
        ]
        for command, action in rows:
            table.add_row(command, action)
        self.console.print(table)
        self.console.print(Panel("也可以直接输入自然语言，例如：查看 Docker 容器状态", border_style="cyan"))

    def _print_agent_answer(self, answer: str) -> None:
        self.console.print(Panel(Markdown(answer), title="Agent", border_style="green", box=box.ROUNDED))

    def _print_user_message(self, message: str) -> None:
        self.console.print(Panel(message, title="You", border_style="blue", box=box.ROUNDED))

    def _print_pending_actions(self, pending: list[dict[str, Any]]) -> None:
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Tool", style="yellow", no_wrap=True)
        table.add_column("Reason")
        for item in pending:
            table.add_row(str(item.get("tool_name")), str(item.get("reason")))
        self.console.print(
            Panel(
                Group(table, Text("确认执行：输入 /approve on 后重新发送同一句请求。", style="yellow")),
                title="Pending Actions",
                border_style="yellow",
            )
        )

    def _print_notice(self, message: str, style: str = "cyan") -> None:
        self.console.print(Panel(message, border_style=style))

    def _print_error(self, message: str) -> None:
        self.console.print(Panel(message, title="Error", border_style="red"))

    @staticmethod
    def _bool_text(value: object) -> str:
        return "[green]true[/green]" if value else "[red]false[/red]"


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
