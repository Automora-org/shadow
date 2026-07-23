from __future__ import annotations

import threading
from typing import Callable

import keyboard


class HotkeyManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handles: list[int] = []
        self._disable = "F8"
        self._enable = "F9"
        self._on_disable: Callable[[], None] | None = None
        self._on_enable: Callable[[], None] | None = None

    def configure(
        self,
        disable_hotkey: str,
        enable_hotkey: str,
        on_disable: Callable[[], None],
        on_enable: Callable[[], None],
    ) -> None:
        with self._lock:
            self._disable = disable_hotkey.strip().upper() or "F8"
            self._enable = enable_hotkey.strip().upper() or "F9"
            self._on_disable = on_disable
            self._on_enable = on_enable
            self._rebind_locked()

    def rebind(self, disable_hotkey: str, enable_hotkey: str) -> None:
        with self._lock:
            self._disable = disable_hotkey.strip().upper() or "F8"
            self._enable = enable_hotkey.strip().upper() or "F9"
            self._rebind_locked()

    def stop(self) -> None:
        with self._lock:
            self._clear_locked()

    def _rebind_locked(self) -> None:
        self._clear_locked()
        if self._on_disable:
            self._handles.append(
                keyboard.add_hotkey(self._disable, self._safe(self._on_disable), suppress=False)
            )
        if self._on_enable:
            self._handles.append(
                keyboard.add_hotkey(self._enable, self._safe(self._on_enable), suppress=False)
            )

    def _clear_locked(self) -> None:
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._handles.clear()

    @staticmethod
    def _safe(cb: Callable[[], None]) -> Callable[[], None]:
        def wrapper() -> None:
            try:
                cb()
            except Exception:
                pass

        return wrapper
