from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


def app_dir() -> Path:
    """Directory for writable app data (config next to exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = app_dir()
CONFIG_PATH = APP_DIR / "config.json"

_EXE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.exe$", re.IGNORECASE)


def _default_pending_dir() -> str:
    return str(Path.home() / ".internal-observer" / "pending") + "\\"


def is_valid_exe_name(name: str) -> bool:
    """Accept only a bare executable filename ending in .exe."""
    value = (name or "").strip()
    if not value or "/" in value or "\\" in value:
        return False
    return bool(_EXE_NAME_RE.fullmatch(value))


def normalize_exe_name(name: str) -> str | None:
    value = (name or "").strip()
    if not is_valid_exe_name(value):
        return None
    return value


@dataclass
class Config:
    process_name: str = "wordpress.exe"
    pending_dir: str = ""
    disable_hotkey: str = "F8"
    enable_hotkey: str = "F9"

    def __post_init__(self) -> None:
        if not self.pending_dir:
            self.pending_dir = _default_pending_dir()
        normalized = normalize_exe_name(self.process_name)
        if normalized is None:
            self.process_name = "wordpress.exe"
        else:
            self.process_name = normalized

    def normalized_process_name(self) -> str:
        return normalize_exe_name(self.process_name) or "wordpress.exe"

    def pending_path(self) -> Path:
        return Path(self.pending_dir)


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        process = str(data.get("process_name", "wordpress.exe"))
        if not is_valid_exe_name(process):
            process = "wordpress.exe"
        return Config(
            process_name=process,
            pending_dir=str(data.get("pending_dir") or _default_pending_dir()),
            disable_hotkey=str(data.get("disable_hotkey", "F8")).upper(),
            enable_hotkey=str(data.get("enable_hotkey", "F9")).upper(),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        cfg = Config()
        save_config(cfg)
        return cfg


def save_config(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
