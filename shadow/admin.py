from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Relaunch this app elevated. Returns True if an elevated process was started."""
    if is_admin():
        return False

    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        rc = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params,
            str(Path(exe).parent),
            1,
        )
        return int(rc) > 32

    extra = " ".join(f'"{a}"' for a in sys.argv[1:])
    params = f"-m shadow {extra}".strip()
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        None,
        1,
    )
    return int(rc) > 32
