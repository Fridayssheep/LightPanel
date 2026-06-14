from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml


COMPOSE_FILENAMES = {
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
}

# 控制目录遍历成本，避开生成产物和第三方依赖目录。
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".svn",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


@dataclass(frozen=True)
class DiscoveredComposeService:
    name: str
    image: str | None = None
    container_name: str | None = None


@dataclass(frozen=True)
class DiscoveredComposeProject:
    name: str
    compose_file: Path
    working_dir: Path
    services: list[DiscoveredComposeService] = field(default_factory=list)


@dataclass(frozen=True)
class ComposeScanResult:
    scan_roots: list[Path]
    projects: list[DiscoveredComposeProject]
    errors: list[str]


def scan_compose_files(roots: Iterable[Path], max_depth: int = 6) -> ComposeScanResult:
    scan_roots: list[Path] = []
    projects: list[DiscoveredComposeProject] = []
    errors: list[str] = []
    seen_files: set[Path] = set()

    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        scan_roots.append(root)

        if not root.exists():
            errors.append(f"{root}: scan root does not exist")
            continue

        if root.is_file():
            if root.name in COMPOSE_FILENAMES:
                _scan_file(root, projects, errors, seen_files)
            else:
                errors.append(f"{root}: scan root is not a recognized Compose file")
            continue

        if not root.is_dir():
            errors.append(f"{root}: scan root is not a directory")
            continue

        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            current_dir = Path(dirpath)
            try:
                depth = len(current_dir.relative_to(root).parts)
            except ValueError:
                dirnames[:] = []
                continue

            if depth >= max_depth:
                # 编排项目通常靠近配置根目录，更深层级大多是依赖或产物。
                dirnames[:] = []
            else:
                # 自顶向下遍历时修改 dirnames 可以告诉 os.walk 跳过哪些子目录。
                dirnames[:] = [
                    name
                    for name in dirnames
                    if name not in SKIP_DIR_NAMES
                    and not name.startswith(".")
                    and not (current_dir / name).is_symlink()
                ]

            for filename in filenames:
                if filename in COMPOSE_FILENAMES:
                    _scan_file(current_dir / filename, projects, errors, seen_files)

    projects.sort(key=lambda item: (item.name.lower(), str(item.compose_file)))
    return ComposeScanResult(scan_roots=scan_roots, projects=projects, errors=errors)


def _scan_file(
    compose_file: Path,
    projects: list[DiscoveredComposeProject],
    errors: list[str],
    seen_files: set[Path],
) -> None:
    resolved_file = compose_file.resolve()
    if resolved_file in seen_files:
        # 多个扫描根目录可能重叠，因此按解析后的真实路径去重。
        return
    seen_files.add(resolved_file)

    try:
        projects.append(_parse_compose_file(resolved_file))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"{resolved_file}: {_one_line(str(exc))}")


def _parse_compose_file(compose_file: Path) -> DiscoveredComposeProject:
    with compose_file.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, dict):
        raise ValueError("top-level YAML document must be a mapping")

    raw_project_name = payload.get("name")
    # 文件没有 name 时，Docker Compose 默认用工作目录名作为项目名。
    project_name = str(raw_project_name).strip() if raw_project_name else compose_file.parent.name
    if not project_name:
        project_name = compose_file.parent.name

    raw_services = payload.get("services") or {}
    if not isinstance(raw_services, dict):
        raise ValueError("services must be a mapping")

    services: list[DiscoveredComposeService] = []
    for raw_name, raw_config in raw_services.items():
        service_name = str(raw_name).strip()
        if not service_name:
            continue

        image: str | None = None
        container_name: str | None = None
        if isinstance(raw_config, dict):
            raw_image = raw_config.get("image")
            raw_container_name = raw_config.get("container_name")
            image = raw_image if isinstance(raw_image, str) and raw_image.strip() else None
            container_name = (
                raw_container_name
                if isinstance(raw_container_name, str) and raw_container_name.strip()
                else None
            )

        services.append(
            DiscoveredComposeService(
                name=service_name,
                image=image,
                container_name=container_name,
            )
        )

    return DiscoveredComposeProject(
        name=project_name,
        compose_file=compose_file,
        working_dir=compose_file.parent,
        services=services,
    )


def _one_line(value: str) -> str:
    return " ".join(value.split())
