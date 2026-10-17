"""Convert the project logo PNG into a multi-resolution Windows icon.

Usage: python tools/make_icon.py
Reads  logo/MailSolo.png
Writes logo/MailSolo.ico
"""

from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / "logo" / "MailSolo.png"
TARGET = PROJECT_ROOT / "logo" / "MailSolo.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not SOURCE.is_file():
        print(f"missing logo: {SOURCE}", file=sys.stderr)
        return 1
    with Image.open(SOURCE) as image:
        rgba = image.convert("RGBA")
        # Square canvas so non-square sources keep their aspect ratio.
        side = max(rgba.size)
        if rgba.size != (side, side):
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(rgba, ((side - rgba.width) // 2, (side - rgba.height) // 2))
            rgba = canvas
        rgba.save(TARGET, format="ICO", sizes=SIZES)
    print(f"icon written: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
