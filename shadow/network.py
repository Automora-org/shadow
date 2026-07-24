from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import psutil

RULE_PREFIX = "ShadowAppBlock"


class NetworkBlocker:
    """Block inbound/outbound traffic for one executable via Windows Firewall."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active = False
        self._blocked = False
        self._process_name = ""
        self._program_path: str | None = None
        self._rule_names: list[str] = []
        self._watch_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_error = ""

    @property
    def active(self) -> bool:
        return self._active

    @property
    def blocked(self) -> bool:
        return self._blocked

    @property
    def program_path(self) -> str | None:
        return self._program_path

    def start(self, process_name: str) -> tuple[bool, str]:
        with self._lock:
            if self._active:
                self._stop_locked()
            self._process_name = process_name
            self._blocked = False
            self._program_path = None
            self._last_error = ""
            self._stop.clear()
            self._active = True
            self._watch_thread = threading.Thread(
                target=self._watch_for_process,
                name="shadow-net-watch",
                daemon=True,
            )
            self._watch_thread.start()

            path = self._resolve_process_path(process_name)
            if not path:
                return (
                    True,
                    f"Waiting for {process_name} to appear, then network will be blocked.",
                )
            ok, msg = self._apply_rules(path)
            if ok:
                return True, msg
            # Keep watching/retrying — common when elevation is missing once.
            return False, msg

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            return self._stop_locked()

    def _stop_locked(self) -> tuple[bool, str]:
        self._stop.set()
        self._active = False
        self._blocked = False
        removed = self._remove_rules()
        self._program_path = None
        self._process_name = ""
        self._last_error = ""
        if removed:
            return True, "Network block removed."
        return True, "Network already allowed."

    def _watch_for_process(self) -> None:
        while not self._stop.wait(2.0):
            with self._lock:
                if not self._active:
                    return
                if self._blocked:
                    continue
                path = self._program_path or self._resolve_process_path(self._process_name)
                if not path:
                    continue
                self._apply_rules(path)

    def _resolve_process_path(self, process_name: str) -> str | None:
        target = process_name.lower()
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name != target:
                    continue
                exe = proc.info.get("exe")
                if exe and Path(exe).is_file():
                    return str(Path(exe).resolve())
            except (psutil.Error, OSError, TypeError, ValueError):
                continue
        return None

    def _apply_rules(self, program_path: str) -> tuple[bool, str]:
        self._remove_rules()
        safe = Path(program_path).stem.replace(" ", "_")
        out_name = f"{RULE_PREFIX}_{safe}_out"
        in_name = f"{RULE_PREFIX}_{safe}_in"
        self._rule_names = [out_name, in_name]
        commands = [
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={out_name}",
                "dir=out",
                "action=block",
                f"program={program_path}",
                "enable=yes",
                "profile=any",
            ],
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={in_name}",
                "dir=in",
                "action=block",
                f"program={program_path}",
                "enable=yes",
                "profile=any",
            ],
        ]
        for cmd in commands:
            code, out = self._run(cmd)
            if code != 0:
                self._remove_rules()
                self._blocked = False
                self._program_path = program_path
                self._last_error = out.strip()
                return (
                    False,
                    "Failed to add firewall rule (run Shadow as Administrator). "
                    + out.strip(),
                )
        self._program_path = program_path
        self._blocked = True
        self._last_error = ""
        return True, f"Blocked network for {program_path}"

    def _remove_rules(self) -> bool:
        removed = False
        names = list(self._rule_names)
        if self._program_path:
            safe = Path(self._program_path).stem.replace(" ", "_")
            names.extend(
                [
                    f"{RULE_PREFIX}_{safe}_out",
                    f"{RULE_PREFIX}_{safe}_in",
                ]
            )
        seen: set[str] = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            code, _ = self._run(
                [
                    "netsh",
                    "advfirewall",
                    "firewall",
                    "delete",
                    "rule",
                    f"name={name}",
                ]
            )
            if code == 0:
                removed = True
        self._rule_names = []
        return removed

    @staticmethod
    def _run(cmd: list[str]) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return completed.returncode, (completed.stdout or "") + (completed.stderr or "")
        except OSError as exc:
            return 1, str(exc)


def cleanup_all_shadow_rules() -> None:
    """Best-effort cleanup of all Shadow firewall rules on exit."""
    code, out = NetworkBlocker._run(
        ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"]
    )
    if code != 0:
        return
    names: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if line.lower().startswith("rule name:"):
            name = line.split(":", 1)[1].strip()
            if name.startswith(RULE_PREFIX):
                names.append(name)
    for name in names:
        NetworkBlocker._run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"]
        )
