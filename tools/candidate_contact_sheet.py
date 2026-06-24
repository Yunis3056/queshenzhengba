from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a contact sheet from a template-candidate manifest.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest
    root = manifest_path.parent
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    output = args.output or root.with_name(f"{root.name}_contact_sheet.png")

    cell_width = 180
    cell_height = 165
    cols = 5
    rows = max(1, math.ceil(len(candidates) / cols))
    sheet = Image.new("RGB", (cols * cell_width, rows * cell_height), "#f7f7f7")
    draw = ImageDraw.Draw(sheet)
    font = _font(12)
    small = _font(10)

    for number, candidate in enumerate(candidates, start=1):
        col = (number - 1) % cols
        row = (number - 1) // cols
        x = col * cell_width
        y = row * cell_height
        path = Path(candidate["path"])
        if not path.is_absolute():
            path = Path.cwd() / path
        draw.rectangle((x + 3, y + 3, x + cell_width - 3, y + cell_height - 3), outline="#cccccc")
        draw.text((x + 8, y + 8), f"{number:02d} {path.name}", fill="#111111", font=small)
        draw.text(
            (x + 8, y + 24),
            f"{candidate['region_key']} rot={candidate.get('rotation_degrees', 0)}",
            fill="#555555",
            font=small,
        )
        if not path.exists():
            draw.text((x + 48, y + 80), "MISSING FILE", fill="#b00020", font=font)
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_width - 20, cell_height - 54), Image.Resampling.LANCZOS)
        sheet.paste(image, (x + (cell_width - image.width) // 2, y + 48))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)
    return 0


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


if __name__ == "__main__":
    raise SystemExit(main())
