from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw


def make_tray_icon(active: bool = False) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = (40, 40, 40, 255) if not active else (180, 40, 40, 255)
    draw.ellipse((4, 4, size - 5, size - 5), fill=fill)
    # Soft highlight
    draw.ellipse((14, 12, 30, 28), fill=(255, 255, 255, 40 if not active else 70))
    return img


def icon_to_bytes(active: bool = False) -> bytes:
    buf = BytesIO()
    make_tray_icon(active).save(buf, format="PNG")
    return buf.getvalue()
