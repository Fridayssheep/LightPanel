from __future__ import annotations

import threading
from collections.abc import Callable

from app.schemas import OverviewResponse


class OverviewCache:
    def __init__(self, collector: Callable[[], OverviewResponse], refresh_interval: float = 5.0):
        self._collector = collector
        self._refresh_interval = refresh_interval
        self._snapshot: OverviewResponse | None = None
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._refresh_requested = threading.Event()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    def get(self) -> OverviewResponse | None:
        with self._lock:
            return self._snapshot

    def refresh_now(self) -> OverviewResponse:
        with self._refresh_lock:
            snapshot = self._collector()
            with self._lock:
                self._snapshot = snapshot
                self.last_error = None
            return snapshot

    def _refresh_safely(self) -> None:
        try:
            self.refresh_now()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.last_error = str(exc)

    def request_refresh(self) -> None:
        self._refresh_requested.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_requested.clear()
        self._refresh_requested.set()
        self._thread = threading.Thread(target=self._run, name="overview-cache-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        self._refresh_requested.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_requested.is_set():
            self._refresh_requested.wait(timeout=self._refresh_interval)
            self._refresh_requested.clear()
            if self._stop_requested.is_set():
                break

            self._refresh_safely()
