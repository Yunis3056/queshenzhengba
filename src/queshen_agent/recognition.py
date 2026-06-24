from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import GameState, Region, RegionConfig, TileObservation
from .paths import MISSING_SUIT_TEMPLATES_DIR, TEMPLATES_DIR
from .tile import ALL_TILES, normalize_suit, sort_tiles


@dataclass(slots=True)
class RecognizerConfig:
    threshold: float = 0.78
    min_tile_width: int = 20
    min_tile_height: int = 28
    max_tile_gap: int = 8
    expected_tile_aspect: float = 0.72
    max_unsplit_aspect: float = 1.2
    expected_hand_counts: tuple[int, ...] = (13, 14)
    missing_suit_threshold: float = 0.78
    missing_suit_margin: float = 0.12


class TemplateRecognizer:
    def __init__(self, template_dir: Path = TEMPLATES_DIR, config: RecognizerConfig | None = None) -> None:
        self.template_dir = template_dir
        self.config = config or RecognizerConfig()
        self.templates = self._load_templates()
        self.missing_suit_templates = self._load_suit_templates()

    def is_ready(self) -> bool:
        return bool(self.templates)

    def missing_templates(self) -> list[str]:
        return [tile for tile in ALL_TILES if tile not in self.templates]

    def recognize_game_state(self, image_path: Path, regions: RegionConfig) -> GameState:
        if not self.templates:
            return GameState(
                recognition_confidence=0.0,
                uncertain_tiles=[],
            )

        base = regions.game_area
        missing_suit = self.recognize_missing_suit(image_path, _relative_region(regions.own_missing_suit, base))
        raw_hand_obs = self.recognize_region(image_path, _relative_region(regions.hand, base), "hand")
        raw_drawn_obs = self.recognize_region(
            image_path,
            _relative_region(regions.drawn_tile, base),
            "drawn_tile",
        )
        raw_self_meld_obs = self.recognize_region(
            image_path,
            _relative_region(regions.self_melds, base),
            "self_melds",
        )
        hand_obs = self._confident_observations(raw_hand_obs)
        drawn_obs = self._confident_observations(raw_drawn_obs)
        self_meld_obs = self._confident_observations(raw_self_meld_obs)

        opponent_discards: dict[str, list[str]] = {"left": [], "top": [], "right": []}
        opponent_melds: dict[str, list[list[str]]] = {"left": [], "top": [], "right": []}

        for seat, region in regions.opponent_discards.items():
            opponent_discards[seat] = [
                obs.tile
                for obs in self._confident_observations(
                    self.recognize_region(
                        image_path,
                        _relative_region(region, base),
                        f"{seat}_discards",
                    )
                )
            ]
        for seat, region in regions.opponent_melds.items():
            tiles = [
                obs.tile
                for obs in self._confident_observations(
                    self.recognize_region(
                        image_path,
                        _relative_region(region, base),
                        f"{seat}_melds",
                    )
                )
            ]
            opponent_melds[seat] = _group_melds(tiles)

        all_obs = list(hand_obs) + list(drawn_obs) + list(self_meld_obs)
        for tiles in opponent_discards.values():
            all_obs.extend(TileObservation(tile=tile, confidence=1.0, region_id="visible") for tile in tiles)
        for melds in opponent_melds.values():
            for meld in melds:
                all_obs.extend(TileObservation(tile=tile, confidence=1.0, region_id="visible") for tile in meld)

        raw_own_obs = raw_hand_obs + raw_drawn_obs + raw_self_meld_obs
        own_obs = hand_obs + drawn_obs + self_meld_obs
        uncertain = [obs for obs in raw_own_obs if obs.confidence < self.config.threshold]
        confidences = [obs.confidence for obs in own_obs]
        confidence = min(confidences) if confidences else 0.0
        hand_display = [
            obs.tile if obs.confidence >= self.config.threshold else "X"
            for obs in raw_hand_obs
        ]
        hand_tiles = [obs.tile for obs in hand_obs]
        if raw_hand_obs and len(hand_tiles) not in self.config.expected_hand_counts:
            confidence = min(confidence, 0.0)
        drawn_tile = drawn_obs[0].tile if drawn_obs else None

        return GameState(
            missing_suit=missing_suit,
            hand=sort_tiles(hand_tiles),
            hand_display=hand_display,
            drawn_tile=drawn_tile,
            self_melds=_group_melds([obs.tile for obs in self_meld_obs]),
            opponent_discards=opponent_discards,
            opponent_melds=opponent_melds,
            visible_tiles=[obs.tile for obs in all_obs],
            recognition_confidence=confidence,
            uncertain_tiles=uncertain,
        )

    def recognize_region(self, image_path: Path, region: Region | None, region_id: str) -> list[TileObservation]:
        if region is None or not region.is_valid() or not self.templates:
            return []

        cv2, np = _require_cv()
        image = cv2.imread(str(image_path))
        if image is None:
            return []
        crop = image[region.y : region.y + region.height, region.x : region.x + region.width]
        if crop.size == 0:
            return []

        tile_boxes = _segment_tile_boxes(crop, self.config)
        observations: list[TileObservation] = []
        for box in tile_boxes:
            x, y, width, height = box
            tile_img = crop[y : y + height, x : x + width]
            tile, confidence = self._match_tile(tile_img)
            observations.append(
                TileObservation(
                    tile=tile,
                    confidence=confidence,
                    region_id=region_id,
                    bbox=Region(region.x + x, region.y + y, width, height),
                )
            )
        return observations

    def _confident_observations(self, observations: list[TileObservation]) -> list[TileObservation]:
        return [obs for obs in observations if obs.confidence >= self.config.threshold]

    def recognize_missing_suit(self, image_path: Path, region: Region | None) -> str | None:
        if region is None or not region.is_valid() or not self.missing_suit_templates:
            return None
        if any(suit not in self.missing_suit_templates for suit in ("m", "p", "s")):
            return None

        cv2, _ = _require_cv()
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        crop = image[region.y : region.y + region.height, region.x : region.x + region.width]
        if crop.size == 0:
            return None

        suit, confidence, runner_up = self._match_template_group_ranked(crop, self.missing_suit_templates)
        if confidence < self.config.missing_suit_threshold:
            return None
        if confidence - runner_up < self.config.missing_suit_margin:
            return None
        return normalize_suit(suit)

    def _load_templates(self) -> dict[str, list[object]]:
        if not self.template_dir.exists():
            return {}
        cv2, _ = _require_cv(soft=True)
        if cv2 is None:
            return {}
        templates: dict[str, list[object]] = {}
        for tile_dir in self.template_dir.iterdir():
            if not tile_dir.is_dir():
                continue
            tile = tile_dir.name
            images = []
            for image_path in tile_dir.glob("*.png"):
                image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    images.append(image)
            if images:
                templates[tile] = images
        return templates

    def _load_suit_templates(self) -> dict[str, list[object]]:
        if not MISSING_SUIT_TEMPLATES_DIR.exists():
            return {}
        cv2, _ = _require_cv(soft=True)
        if cv2 is None:
            return {}
        templates: dict[str, list[object]] = {}
        for suit_dir in MISSING_SUIT_TEMPLATES_DIR.iterdir():
            if not suit_dir.is_dir():
                continue
            suit = normalize_suit(suit_dir.name)
            if suit is None:
                continue
            images = []
            for image_path in suit_dir.glob("*.png"):
                image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    images.append(image)
            if images:
                templates[suit] = images
        return templates

    def _match_tile(self, tile_img: object) -> tuple[str, float]:
        return self._match_template_group(tile_img, self.templates)

    def _match_template_group(self, tile_img: object, templates: dict[str, list[object]]) -> tuple[str, float]:
        best_label, best_score, _ = self._match_template_group_ranked(tile_img, templates)
        return best_label, best_score

    def _match_template_group_ranked(
        self,
        tile_img: object,
        templates: dict[str, list[object]],
    ) -> tuple[str, float, float]:
        cv2, _ = _require_cv()
        gray = cv2.cvtColor(tile_img, cv2.COLOR_BGR2GRAY)
        label_scores: dict[str, float] = {}
        for label, template_images in templates.items():
            label_score = -1.0
            for template in template_images:
                resized = cv2.resize(gray, (template.shape[1], template.shape[0]))
                result = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
                score = float(result.max())
                label_score = max(label_score, score)
            label_scores[label] = label_score
        ranked = sorted(label_scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked:
            return "unknown", 0.0, 0.0
        best_label, best_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        return (
            best_label,
            max(0.0, min(1.0, best_score)),
            max(0.0, min(1.0, runner_up)),
        )


def save_manual_state(path: Path, state: GameState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(state.to_dict(), file, ensure_ascii=False, indent=2)


def ensure_template_dirs(template_dir: Path = TEMPLATES_DIR) -> list[Path]:
    created: list[Path] = []
    for tile in ALL_TILES:
        path = template_dir / tile
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created


def _require_cv(soft: bool = False):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        if soft:
            return None, None
        raise RuntimeError(
            "牌面识别需要安装依赖：python -m pip install -r requirements.txt"
        ) from exc
    return cv2, np


def _relative_region(region: Region | None, base: Region | None) -> Region | None:
    if region is None:
        return None
    if base is None:
        return region
    return Region(
        x=region.x - base.x,
        y=region.y - base.y,
        width=region.width,
        height=region.height,
    )


def _segment_tile_boxes(crop: object, config: RecognizerConfig) -> list[tuple[int, int, int, int]]:
    cv2, np = _require_cv()
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width >= config.min_tile_width and height >= config.min_tile_height:
            boxes.append((x, y, width, height))

    if not boxes:
        return []

    boxes.sort(key=lambda box: (box[1] // max(1, config.min_tile_height), box[0]))
    merged = _merge_close_boxes(boxes, config.max_tile_gap)
    split = _split_wide_boxes(merged, config)
    return sorted(split, key=lambda box: (box[1] // max(1, config.min_tile_height), box[0]))


def _merge_close_boxes(boxes: list[tuple[int, int, int, int]], max_gap: int) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in boxes:
        x, y, width, height = box
        if not merged:
            merged.append(box)
            continue
        px, py, pw, ph = merged[-1]
        same_row = abs((py + ph / 2) - (y + height / 2)) < max(ph, height) * 0.4
        gap = x - (px + pw)
        if same_row and 0 <= gap <= max_gap:
            nx = min(px, x)
            ny = min(py, y)
            nr = max(px + pw, x + width)
            nb = max(py + ph, y + height)
            merged[-1] = (nx, ny, nr - nx, nb - ny)
        else:
            merged.append(box)
    return merged


def _split_wide_boxes(
    boxes: list[tuple[int, int, int, int]],
    config: RecognizerConfig,
) -> list[tuple[int, int, int, int]]:
    split: list[tuple[int, int, int, int]] = []
    for x, y, width, height in boxes:
        aspect = width / max(1, height)
        if aspect <= config.max_unsplit_aspect:
            split.append((x, y, width, height))
            continue

        estimated_width = max(config.min_tile_width, round(height * config.expected_tile_aspect))
        count = round(width / estimated_width)
        if count < 2:
            split.append((x, y, width, height))
            continue

        for index in range(count):
            left = x + round(index * width / count)
            right = x + round((index + 1) * width / count)
            tile_width = right - left
            if tile_width >= config.min_tile_width:
                split.append((left, y, tile_width, height))
    return split


def _group_melds(tiles: list[str]) -> list[list[str]]:
    if not tiles:
        return []
    groups: list[list[str]] = []
    current: list[str] = []
    for tile in tiles:
        if not current or tile == current[-1]:
            current.append(tile)
        else:
            groups.append(current)
            current = [tile]
    if current:
        groups.append(current)
    return groups
