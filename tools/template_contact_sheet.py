from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PIL import Image, ImageDraw, ImageFont

from queshen_agent.paths import PROJECT_ROOT, TEMPLATES_DIR
from queshen_agent.tile import ALL_TILES, tile_label


OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_IMAGE = OUTPUT_DIR / "template_contact_sheet.png"
OUTPUT_TEXT = OUTPUT_DIR / "template_coverage.txt"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font = _font(18)
    small_font = _font(13)
    cell_width = 150
    cell_height = 156
    cols = 9
    rows = 3
    sheet = Image.new("RGB", (cols * cell_width, rows * cell_height), "#f5f5f5")
    draw = ImageDraw.Draw(sheet)
    lines = []

    for index, tile in enumerate(ALL_TILES):
        col = index % cols
        row = index // cols
        x = col * cell_width
        y = row * cell_height
        tile_dir = TEMPLATES_DIR / tile
        samples = sorted(tile_dir.glob("*.png")) if tile_dir.exists() else []
        draw.rectangle((x + 4, y + 4, x + cell_width - 4, y + cell_height - 4), outline="#cccccc")
        title = f"{tile} {tile_label(tile)}"
        draw.text((x + 12, y + 10), title, fill="#202020", font=font)
        draw.text((x + 12, y + 34), f"{len(samples)} samples", fill="#666666", font=small_font)
        if samples:
            thumb = Image.open(samples[0]).convert("RGB")
            thumb.thumbnail((76, 92), Image.Resampling.LANCZOS)
            tx = x + (cell_width - thumb.width) // 2
            ty = y + 58
            sheet.paste(thumb, (tx, ty))
            lines.append(f"{tile}\t{tile_label(tile)}\t{len(samples)}\t{samples[0]}")
        else:
            draw.text((x + 50, y + 88), "MISSING", fill="#b00020", font=small_font)
            lines.append(f"{tile}\t{tile_label(tile)}\t0\tMISSING")

    sheet.save(OUTPUT_IMAGE)
    OUTPUT_TEXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT_IMAGE)
    print(OUTPUT_TEXT)
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
