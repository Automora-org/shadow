from __future__ import annotations

import threading
from typing import Callable

from .capture import CaptureBundle, capture_screen_bundle
from .config import Config
from .hotkeys import HotkeyManager
from .network import NetworkBlocker, cleanup_all_shadow_rules
from .watcher import PendingReplacer


StatusCallback = Callable[[str], None]
StateCallback = Callable[[bool], None]


class ShadowController:
    def __init__(
        self,
        config: Config,
        on_status: StatusCallback | None = None,
        on_state: StateCallback | None = None,
    ) -> None:
        self.config = config
        self.on_status = on_status or (lambda _msg: None)
        self.on_state = on_state or (lambda _active: None)
        self._lock = threading.RLock()
        self._shadow_active = False
        self._bundle: CaptureBundle | None = None
        self._replacer: PendingReplacer | None = None
        self._blocker = NetworkBlocker()
        self._hotkeys = HotkeyManager()

    @property
    def shadow_active(self) -> bool:
        return self._shadow_active

    def start_hotkeys(self) -> None:
        self._hotkeys.configure(
            self.config.disable_hotkey,
            self.config.enable_hotkey,
            on_disable=self.activate_shadow,
            on_enable=self.deactivate_shadow,
        )

    def pause_hotkeys(self) -> None:
        self._hotkeys.pause()

    def resume_hotkeys(self) -> None:
        self._hotkeys.resume()

    def update_config(self, config: Config, *, reapply_if_active: bool = True) -> None:
        with self._lock:
            was_active = self._shadow_active
            process_changed = (
                config.normalized_process_name() != self.config.normalized_process_name()
            )
            pending_changed = config.pending_path() != self.config.pending_path()
            hotkeys_changed = (
                config.disable_hotkey.lower() != self.config.disable_hotkey.lower()
                or config.enable_hotkey.lower() != self.config.enable_hotkey.lower()
            )
            if was_active and reapply_if_active and (process_changed or pending_changed):
                self._deactivate_locked(notify=False)
            self.config = config
            if hotkeys_changed:
                self._hotkeys.rebind(config.disable_hotkey, config.enable_hotkey)
            if was_active and reapply_if_active and (process_changed or pending_changed):
                self._activate_locked()

    def activate_shadow(self) -> None:
        with self._lock:
            self._activate_locked()

    def deactivate_shadow(self) -> None:
        with self._lock:
            self._deactivate_locked(notify=True)

    def shutdown(self) -> None:
        with self._lock:
            self._deactivate_locked(notify=False)
            self._hotkeys.stop()
            cleanup_all_shadow_rules()

    def _activate_locked(self) -> None:
        if self._shadow_active:
            self._emit("Shadow already active.")
            return
        try:
            bundle = capture_screen_bundle()
        except Exception as exc:
            self._emit(f"Screenshot failed: {exc}")
            return

        pending = self.config.pending_path()
        replacer = PendingReplacer(pending, bundle)
        try:
            replacer.start()
        except Exception as exc:
            self._emit(f"Pending watcher failed: {exc}")
            return

        ok, msg = self._blocker.start(self.config.normalized_process_name())
        self._bundle = bundle
        self._replacer = replacer
        self._shadow_active = True
        self._emit_state(True)
        if not ok:
            self._emit(f"Shadow ON (network warn): {msg}")
        else:
            self._emit(f"Shadow ON. {msg}")

    def _deactivate_locked(self, notify: bool) -> None:
        if self._replacer is not None:
            try:
                self._replacer.stop()
            except Exception:
                pass
            self._replacer = None
        try:
            _, msg = self._blocker.stop()
        except Exception as exc:
            msg = str(exc)
        self._bundle = None
        was = self._shadow_active
        self._shadow_active = False
        if was:
            self._emit_state(False)
        if notify and was:
            self._emit(f"Shadow OFF. {msg}")
        elif notify and not was:
            self._emit("Shadow already off.")

    def _emit(self, message: str) -> None:
        try:
            self.on_status(message)
        except Exception:
            pass

    def _emit_state(self, active: bool) -> None:
        try:
            self.on_state(active)
        except Exception:
            pass
