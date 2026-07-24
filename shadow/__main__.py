from __future__ import annotations

import atexit
import sys

from .admin import is_admin, relaunch_as_admin
from .config import load_config
from .controller import ShadowController
from .network import cleanup_all_shadow_rules
from .tray import TrayService
from .ui import ShadowApp


def main() -> int:
    if sys.platform != "win32":
        print("Shadow is Windows-only.")
        return 1

    if not is_admin():
        if relaunch_as_admin():
            return 0
        print("Warning: not running as Administrator — network block may fail.")

    config = load_config()
    app_holder: dict[str, ShadowApp] = {}
    tray_holder: dict[str, TrayService] = {}

    def set_status(message: str) -> None:
        app = app_holder.get("app")
        if app is not None:
            app.after(0, lambda: app.set_status(message))
        tray = tray_holder.get("tray")
        if tray is not None and (
            message.startswith("Shadow ON") or message.startswith("Shadow OFF")
        ):
            tray.notify("Shadow", message)

    def set_state(active: bool) -> None:
        app = app_holder.get("app")
        tray = tray_holder.get("tray")

        def apply() -> None:
            if tray is not None:
                tray.set_active(active)

        if app is not None:
            app.after(0, apply)
        else:
            apply()

    controller = ShadowController(config, on_status=set_status, on_state=set_state)

    def show_window() -> None:
        app = app_holder.get("app")
        if app is not None:
            app.after(0, app.show_window)

    def exit_app() -> None:
        controller.shutdown()
        tray = tray_holder.get("tray")
        if tray is not None:
            tray.stop()
        app = app_holder.get("app")
        if app is not None:
            app.after(0, app.destroy)

    tray = TrayService(
        on_show=show_window,
        on_shadow_on=controller.activate_shadow,
        on_shadow_off=controller.deactivate_shadow,
        on_exit=exit_app,
    )
    tray_holder["tray"] = tray

    app = ShadowApp(controller, on_hide=lambda: tray.notify("Shadow", "Running in tray."))
    app_holder["app"] = app

    atexit.register(cleanup_all_shadow_rules)
    atexit.register(controller.shutdown)

    controller.start_hotkeys()
    tray.start()

    if not is_admin():
        app.set_status("Ready (not admin — firewall block may fail). Shadow is OFF.")

    app.mainloop()
    controller.shutdown()
    tray.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
