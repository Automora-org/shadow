from __future__ import annotations

import threading
from typing import Callable

import keyboard


def to_keyboard_hotkey(raw: str) -> str:
    """Normalize to keyboard-module form: f8, ctrl+shift+f1, etc."""
    parts = [p.strip().lower() for p in (raw or "").replace(" ", "").split("+") if p.strip()]
    if not parts:
        return ""
    mapped: list[str] = []
    for part in parts:
        if part in {"control", "ctl"}:
            mapped.append("ctrl")
        elif part in {"windows", "left windows", "right windows", "win"}:
            mapped.append("windows")
        else:
            mapped.append(part)
    return "+".join(mapped)


def format_hotkey_display(hotkey: str) -> str:
    if not hotkey:
        return ""
    out: list[str] = []
    for part in to_keyboard_hotkey(hotkey).split("+"):
        if part == "ctrl":
            out.append("Ctrl")
        elif part == "alt":
            out.append("Alt")
        elif part == "shift":
            out.append("Shift")
        elif part == "windows":
            out.append("Win")
        elif part.startswith("f") and part[1:].isdigit():
            out.append(part.upper())
        elif len(part) == 1:
            out.append(part.upper())
        else:
            out.append(part.capitalize())
    return "+".join(out)


def capture_hotkey_blocking() -> str:
    """Block until a hotkey combination is pressed."""
    return to_keyboard_hotkey(keyboard.read_hotkey(suppress=False))


class HotkeyManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handles: list[int | str] = []
        self._disable = "f8"
        self._enable = "f9"
        self._on_disable: Callable[[], None] | None = None
        self._on_enable: Callable[[], None] | None = None
        self._paused = False

    def configure(
        self,
        disable_hotkey: str,
        enable_hotkey: str,
        on_disable: Callable[[], None],
        on_enable: Callable[[], None],
    ) -> None:
        with self._lock:
            self._disable = to_keyboard_hotkey(disable_hotkey) or "f8"
            self._enable = to_keyboard_hotkey(enable_hotkey) or "f9"
            self._on_disable = on_disable
            self._on_enable = on_enable
            if not self._paused:
                self._rebind_locked()

    def rebind(self, disable_hotkey: str, enable_hotkey: str) -> None:
        with self._lock:
            self._disable = to_keyboard_hotkey(disable_hotkey) or "f8"
            self._enable = to_keyboard_hotkey(enable_hotkey) or "f9"
            if not self._paused:
                self._rebind_locked()

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            self._clear_locked()

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self._rebind_locked()

    def stop(self) -> None:
        with self._lock:
            self._paused = True
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
