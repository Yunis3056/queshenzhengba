from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import Region
from .paths import SCREENSHOTS_DIR


def _require_pillow_mss():
    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "截图功能需要安装依赖：python -m pip install -r requirements.txt"
        ) from exc
    return mss, Image


def capture_region(region: Region | None, output_dir: Path = SCREENSHOTS_DIR) -> Path:
    if region is None or not region.is_valid():
        raise ValueError("请先选择一个有效的游戏区域。")

    mss, Image = _require_pillow_mss()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = output_dir / f"queshen_{timestamp}.png"

    monitor = {
        "left": region.x,
        "top": region.y,
        "width": region.width,
        "height": region.height,
    }
    with mss.mss() as screen:
        shot = screen.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        image.save(path)
    return path


def crop_region(image_path: Path, region: Region, output_path: Path) -> Path:
    _, Image = _require_pillow_mss()
    with Image.open(image_path) as image:
        cropped = image.crop((region.x, region.y, region.x + region.width, region.y + region.height))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_path)
    return output_path
