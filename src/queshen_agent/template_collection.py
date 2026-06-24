from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from .models import Region, RegionConfig
from .paths import SAMPLES_DIR, TEMPLATES_DIR
from .tile import ALL_TILES, normalize_tile


CANDIDATES_DIR = SAMPLES_DIR / "template_candidates"
DEFAULT_TEMPLATE_REGION_KEYS = ("hand", "drawn_tile", "self_melds")
OPPONENT_TEMPLATE_REGION_KEYS = (
    "opponent_discards.left",
    "opponent_discards.top",
    "opponent_discards.right",
    "opponent_melds.left",
    "opponent_melds.top",
    "opponent_melds.right",
    "center_discards",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(slots=True)
class CandidateCrop:
    region_key: str
    index: int
    bbox: Region
    path: Path
    rotation_degrees: int = 0
    bbox_space: str = "upright_region"

    def to_dict(self) -> dict[str, object]:
        return {
            "region_key": self.region_key,
            "index": self.index,
            "bbox": self.bbox.to_dict(),
            "path": str(self.path),
            "rotation_degrees": self.rotation_degrees,
            "bbox_space": self.bbox_space,
        }


@dataclass(slots=True)
class CandidateExport:
    output_dir: Path
    manifest_path: Path
    region_crops: dict[str, Path]
    previews: dict[str, Path]
    candidates: list[CandidateCrop]


def find_latest_screenshot(paths: Iterable[Path]) -> Path | None:
    images: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            images.append(path)
        elif path.exists():
            images.extend(
                child
                for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
            )
    if not images:
        return None
    return max(images, key=lambda image: image.stat().st_mtime)


def template_region_keys(include_opponents: bool = False) -> tuple[str, ...]:
    if include_opponents:
        return DEFAULT_TEMPLATE_REGION_KEYS + OPPONENT_TEMPLATE_REGION_KEYS
    return DEFAULT_TEMPLATE_REGION_KEYS


def rotation_for_region_key(region_key: str) -> int:
    if region_key.endswith(".left"):
        return 90
    if region_key.endswith(".right"):
        return -90
    if region_key.endswith(".top"):
        return 180
    return 0


def region_for_key(regions: RegionConfig, key: str) -> Region | None:
    region: Region | None
    if key in {
        "hand",
        "drawn_tile",
        "self_melds",
        "dingque",
        "turn_timer",
        "self_info",
        "center_discards",
    }:
        region = getattr(regions, key)
    elif key.startswith("opponent_discards."):
        seat = key.split(".", 1)[1]
        region = regions.opponent_discards.get(seat)
    elif key.startswith("opponent_melds."):
        seat = key.split(".", 1)[1]
        region = regions.opponent_melds.get(seat)
    elif key.startswith("player_info."):
        seat = key.split(".", 1)[1]
        region = regions.player_info.get(seat)
    else:
        raise KeyError(f"Unknown region key: {key}")

    if region is None:
        return None
    return _relative_to_game_area(region, regions.game_area)


def save_template_crop(
    image_path: Path,
    bbox: Region,
    tile: str,
    template_dir: Path = TEMPLATES_DIR,
    *,
    prefix: str = "sample",
    padding: int = 0,
) -> Path:
    normalized_tile = normalize_tile(tile)
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        crop_box = _region_to_box(_expand_region(bbox, padding), image.size)
        if crop_box is None:
            raise ValueError("Selected crop is outside the image.")
        crop = image.crop(crop_box)

    tile_dir = template_dir / normalized_tile
    tile_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_source = _safe_stem(image_path.stem)
    output = tile_dir / f"{prefix}_{safe_source}_{timestamp}.png"
    crop.save(output)
    return output


def collect_template_candidates(
    image_path: Path,
    regions: RegionConfig,
    output_dir: Path = CANDIDATES_DIR,
    *,
    region_keys: Iterable[str] = DEFAULT_TEMPLATE_REGION_KEYS,
) -> CandidateExport:
    output_dir = output_dir / _safe_stem(image_path.stem)
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as source:
        source_image = source.convert("RGB")

    region_crops: dict[str, Path] = {}
    previews: dict[str, Path] = {}
    candidates: list[CandidateCrop] = []

    for region_key in region_keys:
        region = region_for_key(regions, region_key)
        clipped = _clip_region(region, source_image.size) if region else None
        if clipped is None:
            continue

        file_key = _safe_stem(region_key)
        rotation = rotation_for_region_key(region_key)
        region_crop = source_image.crop(_region_to_tuple(clipped))
        region_crop_path = output_dir / f"{file_key}_region.png"
        region_crop.save(region_crop_path)
        region_crops[region_key] = region_crop_path
        upright_crop = _rotate_crop(region_crop, rotation)
        upright_region_crop_path = output_dir / f"{file_key}_upright_region.png"
        upright_crop.save(upright_region_crop_path)

        boxes = _segment_candidate_boxes_in_image(upright_crop)
        preview = upright_crop.copy()
        draw = ImageDraw.Draw(preview)

        for index, box in enumerate(boxes, start=1):
            crop_path = output_dir / f"{file_key}_{index:02d}_unknown.png"
            crop = upright_crop.crop(_region_to_tuple(box))
            crop.save(crop_path)
            candidates.append(CandidateCrop(region_key, index, box, crop_path, rotation))
            draw.rectangle(_region_to_tuple(box), outline="#f2c572", width=2)
            draw.text((box.x + 3, box.y + 3), str(index), fill="#f2c572")

        preview_path = output_dir / f"{file_key}_preview.png"
        preview.save(preview_path)
        previews[region_key] = preview_path

    manifest_path = output_dir / "manifest.json"
    manifest = {
        "source_image": str(image_path),
        "output_dir": str(output_dir),
        "region_crops": {key: str(path) for key, path in region_crops.items()},
        "previews": {key: str(path) for key, path in previews.items()},
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return CandidateExport(output_dir, manifest_path, region_crops, previews, candidates)


def _segment_candidate_boxes_in_image(image: Image.Image) -> list[Region]:
    try:
        from .recognition import RecognizerConfig, _require_cv, _segment_tile_boxes

        cv2, np = _require_cv(soft=True)
        if cv2 is None:
            return []
        crop = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        boxes = _segment_tile_boxes(crop, RecognizerConfig())
    except Exception:
        return []
    return [Region(x, y, width, height) for x, y, width, height in boxes]


def _relative_to_game_area(region: Region, game_area: Region | None) -> Region:
    if game_area is None:
        return region
    return Region(
        x=region.x - game_area.x,
        y=region.y - game_area.y,
        width=region.width,
        height=region.height,
    )


def _expand_region(region: Region, padding: int) -> Region:
    if padding <= 0:
        return region
    return Region(
        x=region.x - padding,
        y=region.y - padding,
        width=region.width + padding * 2,
        height=region.height + padding * 2,
    )


def _clip_region(region: Region, image_size: tuple[int, int]) -> Region | None:
    image_width, image_height = image_size
    left = max(0, region.x)
    top = max(0, region.y)
    right = min(image_width, region.x + region.width)
    bottom = min(image_height, region.y + region.height)
    if right <= left or bottom <= top:
        return None
    return Region(left, top, right - left, bottom - top)


def _region_to_box(region: Region, image_size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    clipped = _clip_region(region, image_size)
    if clipped is None:
        return None
    return _region_to_tuple(clipped)


def _region_to_tuple(region: Region) -> tuple[int, int, int, int]:
    return (region.x, region.y, region.x + region.width, region.y + region.height)


def _rotate_crop(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image
    return image.rotate(degrees, expand=True)


def _safe_stem(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)[:80]
