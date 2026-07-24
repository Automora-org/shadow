from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw


def make_tray_icon(active: bool = False) -> Image.Image:
    """Gray/blue when Shadow OFF, vivid red when Shadow ON."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if active:
        fill = (220, 48, 48, 255)
        rim = (255, 140, 140, 255)
        highlight = (255, 255, 255, 90)
    else:
        fill = (56, 92, 140, 255)
        rim = (120, 160, 210, 255)
        highlight = (255, 255, 255, 50)
    draw.ellipse((2, 2, size - 3, size - 3), fill=rim)
    draw.ellipse((8, 8, size - 9, size - 9), fill=fill)
    draw.ellipse((16, 14, 30, 28), fill=highlight)
    return img


def icon_to_bytes(active: bool = False) -> bytes:
    buf = BytesIO()
    make_tray_icon(active).save(buf, format="PNG")
    return buf.getvalue()
