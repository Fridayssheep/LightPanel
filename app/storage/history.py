from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.schemas import IncidentRecord


class IncidentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all_unlocked(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            # 历史文件损坏不应拖垮 API，直接按空历史处理。
            return []
        return payload if isinstance(payload, list) else []

    def save(self, incident: IncidentRecord) -> None:
        with self._lock:
            items = self._read_all_unlocked()
            items.append(incident.model_dump(mode="json"))
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(items, file, ensure_ascii=False, indent=2)

    def list(self, limit: int = 50) -> list[IncidentRecord]:
        with self._lock:
            items = self._read_all_unlocked()
        records = [IncidentRecord.model_validate(item) for item in items]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            items = self._read_all_unlocked()
        for item in items:
            if item.get("incident_id") == incident_id:
                return IncidentRecord.model_validate(item)
        return None

    def session_until(self, incident_id: str) -> list[IncidentRecord]:
        with self._lock:
            items = self._read_all_unlocked()

        records = [IncidentRecord.model_validate(item) for item in items]
        source = next((record for record in records if record.incident_id == incident_id), None)
        if not source:
            return []

        session_records = [record for record in records if record.session_id == source.session_id]
        session_records.sort(key=lambda record: record.created_at)

        history: list[IncidentRecord] = []
        for record in session_records:
            history.append(record)
            if record.incident_id == incident_id:
                # 截止到选中的事件，避免续聊时带入之后不相关的对话。
                break
        return history

    def delete(self, incident_id: str) -> bool:
        with self._lock:
            items = self._read_all_unlocked()
            kept = [item for item in items if item.get("incident_id") != incident_id]
            if len(kept) == len(items):
                return False
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(kept, file, ensure_ascii=False, indent=2)
            return True

    def similar_by_message(self, message: str, limit: int = 3) -> list[IncidentRecord]:
        # 轻量本地召回只作为模型提示，不代表当前机器事实。
        tokens = {token for token in message.lower().replace("/", " ").split() if len(token) > 2}
        if not tokens:
            return []
        candidates: list[tuple[int, IncidentRecord]] = []
        for item in self.list(limit=200):
            text = f"{item.user_message} {item.answer}".lower()
            score = sum(1 for token in tokens if token in text)
            if score:
                candidates.append((score, item))
        candidates.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
        return [record for _, record in candidates[:limit]]
