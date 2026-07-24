from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

user32 = ctypes.windll.user32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

_OVERLAY_RED = (255, 0, 0)
_TARGET_WIDTH = 1200
# Inter regular size tuned for 1200px-wide observer-style captures.
_FONT_SIZE_AT_1200 = 24
_LINE_GAP_AT_1200 = 4
_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|^\\\\\\\\")


@dataclass
class CaptureBundle:
    """Frozen observer-style capture used while shadow mode is active."""

    base_image: Image.Image  # RGB screenshot without timestamp overlay
    caption: str
    clicks: str = "0"
    keyboards: str = "0"
    activity: str = "idle"
    captured_at: datetime = field(default_factory=datetime.now)


def normalize_window_title(title: str) -> str:
    """Use window title only — never a full filesystem path."""
    t = (title or "").strip() or "Desktop"
    if _PATH_RE.match(t) or t.count("\\") >= 2 or (t.startswith("/") and t.count("/") >= 2):
        leaf = Path(t.replace("/", "\\")).name.strip()
        if leaf:
            return leaf[:80]
    return t[:80]


def get_foreground_title() -> str:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "Desktop"
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return "Desktop"
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return normalize_window_title(buf.value or "")


def _bundled_font_path() -> Path | None:
    """Resolve Inter font from package assets (dev, wheel, or frozen exe)."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(getattr(sys, "_MEIPASS"))
        candidates.append(meipass / "shadow" / "assets" / "Inter-Regular.ttf")
        candidates.append(meipass / "assets" / "Inter-Regular.ttf")
        candidates.append(meipass / "Inter-Regular.ttf")
    pkg_dir = Path(__file__).resolve().parent
    candidates.append(pkg_dir / "assets" / "Inter-Regular.ttf")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _load_overlay_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    bundled = _bundled_font_path()
    candidates: list[str] = []
    if bundled is not None:
        candidates.append(str(bundled))
    # Fallbacks if the bundled file is missing.
    candidates.extend(
        [
            r"C:\Windows\Fonts\Inter-Regular.ttf",
            r"C:\Windows\Fonts\Inter.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_observer_overlay(
    base: Image.Image,
    ts: datetime,
    window_name: str,
    *,
    keys: int = 0,
    mouse: int = 0,
) -> Image.Image:
    """Draw red bottom-left overlay matching Internal Observer style."""
    img = base.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    scale = img.width / float(_TARGET_WIDTH)
    font_size = max(14, int(round(_FONT_SIZE_AT_1200 * scale)))
    line_gap = max(2, int(round(_LINE_GAP_AT_1200 * scale)))
    font = _load_overlay_font(font_size)
    title = normalize_window_title(window_name)
    lines = [
        ts.strftime("%Y-%m-%d %H:%M:%S"),
        f"Keys: {keys} | Mouse: {mouse}",
        title,
    ]
    heights: list[int] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        heights.append(bbox[3] - bbox[1])
    block_h = sum(heights) + line_gap * (len(lines) - 1)
    margin_x = max(8, int(round(14 * scale)))
    margin_y = max(8, int(round(16 * scale)))
    y = img.height - margin_y - block_h
    for line, h in zip(lines, heights):
        # Explicit zero stroke keeps weight closer to observer GDI text.
        draw.text((margin_x, y), line, fill=_OVERLAY_RED, font=font, stroke_width=0)
        y += h + line_gap
    return img


def encode_jpeg(image: Image.Image, *, quality: int = 85) -> bytes:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def capture_screen_bundle() -> CaptureBundle:
    shot = ImageGrab.grab(all_screens=True).convert("RGB")
    if shot.width > _TARGET_WIDTH:
        ratio = _TARGET_WIDTH / float(shot.width)
        shot = shot.resize(
            (_TARGET_WIDTH, max(1, int(shot.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    title = get_foreground_title()
    now = datetime.now()
    return CaptureBundle(
        base_image=shot,
        caption=title,
        clicks="0",
        keyboards="0",
        activity="idle",
        captured_at=now,
    )


def render_bundle_jpeg(bundle: CaptureBundle, ts: datetime) -> bytes:
    """Same frozen screen, overlay timestamp updated to ``ts``; keys/mouse stay 0."""
    stamped = draw_observer_overlay(
        bundle.base_image,
        ts,
        bundle.caption,
        keys=0,
        mouse=0,
    )
    return encode_jpeg(stamped)


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
    paths[0].write_bytes(render_bundle_jpeg(bundle, when))
    paths[1].write_text(bundle.caption, encoding="utf-8")
    paths[2].write_text("0", encoding="utf-8")
    paths[3].write_text("0", encoding="utf-8")
    return paths
