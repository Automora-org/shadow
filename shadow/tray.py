from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image

from .icons import make_tray_icon


class TrayService:
    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        on_shadow_on: Callable[[], None],
        on_shadow_off: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_show = on_show
        self.on_shadow_on = on_shadow_on
        self.on_shadow_off = on_shadow_off
        self.on_exit = on_exit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._active = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="shadow-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

    def set_active(self, active: bool) -> None:
        self._active = active
        if self._icon is not None:
            try:
                self._icon.icon = make_tray_icon(active)
                self._icon.title = "Shadow — ON" if active else "Shadow — OFF"
            except Exception:
                pass

    def notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title)
        except Exception:
            pass

    def _run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Open Shadow", self._show, default=True),
            pystray.MenuItem("Shadow ON", lambda: self.on_shadow_on()),
            pystray.MenuItem("Shadow OFF", lambda: self.on_shadow_off()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )
        self._icon = pystray.Icon(
            "Shadow",
            make_tray_icon(False),
            "Shadow — OFF",
            menu,
        )
        self._icon.run()

    def _show(self, _icon: pystray.Icon | None = None, _item: object = None) -> None:
        self.on_show()

    def _exit(self, _icon: pystray.Icon | None = None, _item: object = None) -> None:
        self.on_exit()
