from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageGrab

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int


@dataclass
class CaptureBundle:
    """Frozen observer-style capture used while shadow mode is active."""

    image_bytes: bytes
    caption: str
    clicks: str
    keyboards: str
    activity: str  # "work" | "idle"
    captured_at: datetime


def get_foreground_title() -> str:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "Desktop"
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return "Desktop"
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = (buf.value or "").strip()
    return title or "Desktop"


def capture_screen_bundle() -> CaptureBundle:
    shot = ImageGrab.grab(all_screens=True)
    # Match observer-ish sizing while keeping readability.
    max_w = 1200
    if shot.width > max_w:
        ratio = max_w / float(shot.width)
        shot = shot.resize(
            (max_w, max(1, int(shot.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buf = BytesIO()
    shot.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
    title = get_foreground_title()
    return CaptureBundle(
        image_bytes=buf.getvalue(),
        caption=title[:200],
        clicks="0",
        keyboards="0",
        activity="work",
        captured_at=datetime.now(),
    )


def bundle_filenames(ts: datetime, activity: str) -> tuple[str, str, str, str]:
    stamp = ts.strftime("%Y%m%d_%H%M%S")
    base = f"screenshot_{stamp}-{activity}.jpg"
    return base, f"{base}.caption", f"{base}.clicks", f"{base}.keyboards"


def write_bundle(pending_dir: Path, bundle: CaptureBundle, ts: datetime | None = None) -> list[Path]:
    pending_dir.mkdir(parents=True, exist_ok=True)
    when = ts or datetime.now()
    jpg_name, cap_name, clicks_name, keys_name = bundle_filenames(when, bundle.activity)
    paths = [
        pending_dir / jpg_name,
        pending_dir / cap_name,
        pending_dir / clicks_name,
        pending_dir / keys_name,
    ]
    paths[0].write_bytes(bundle.image_bytes)
    paths[1].write_text(bundle.caption, encoding="utf-8")
    paths[2].write_text(bundle.clicks, encoding="utf-8")
    paths[3].write_text(bundle.keyboards, encoding="utf-8")
    return paths
