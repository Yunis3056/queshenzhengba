from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .tile import normalize_suit, normalize_tiles


@dataclass(slots=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Region | None":
        if not data:
            return None
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


@dataclass(slots=True)
class RegionConfig:
    game_area: Region | None = None
    hand: Region | None = None
    drawn_tile: Region | None = None
    self_melds: Region | None = None
    dingque: Region | None = None
    own_missing_suit: Region | None = None
    turn_timer: Region | None = None
    self_info: Region | None = None
    center_discards: Region | None = None
    opponent_discards: dict[str, Region | None] = field(
        default_factory=lambda: {"left": None, "top": None, "right": None}
    )
    opponent_melds: dict[str, Region | None] = field(
        default_factory=lambda: {"left": None, "top": None, "right": None}
    )
    player_info: dict[str, Region | None] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionConfig":
        return cls(
            game_area=Region.from_dict(data.get("game_area")),
            hand=Region.from_dict(data.get("hand")),
            drawn_tile=Region.from_dict(data.get("drawn_tile")),
            self_melds=Region.from_dict(data.get("self_melds")),
            dingque=Region.from_dict(data.get("dingque")),
            own_missing_suit=Region.from_dict(data.get("own_missing_suit")),
            turn_timer=Region.from_dict(data.get("turn_timer")),
            self_info=Region.from_dict(data.get("self_info")),
            center_discards=Region.from_dict(data.get("center_discards")),
            opponent_discards={
                seat: Region.from_dict(region)
                for seat, region in data.get("opponent_discards", {}).items()
            }
            or {"left": None, "top": None, "right": None},
            opponent_melds={
                seat: Region.from_dict(region)
                for seat, region in data.get("opponent_melds", {}).items()
            }
            or {"left": None, "top": None, "right": None},
            player_info={
                seat: Region.from_dict(region)
                for seat, region in data.get("player_info", {}).items()
            },
            ui=dict(data.get("ui", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        def region_to_dict(region: Region | None) -> dict[str, int] | None:
            return region.to_dict() if region else None

        return {
            "game_area": region_to_dict(self.game_area),
            "hand": region_to_dict(self.hand),
            "drawn_tile": region_to_dict(self.drawn_tile),
            "self_melds": region_to_dict(self.self_melds),
            "dingque": region_to_dict(self.dingque),
            "own_missing_suit": region_to_dict(self.own_missing_suit),
            "turn_timer": region_to_dict(self.turn_timer),
            "self_info": region_to_dict(self.self_info),
            "center_discards": region_to_dict(self.center_discards),
            "opponent_discards": {
                seat: region_to_dict(region)
                for seat, region in self.opponent_discards.items()
            },
            "opponent_melds": {
                seat: region_to_dict(region)
                for seat, region in self.opponent_melds.items()
            },
            "player_info": {
                seat: region_to_dict(region)
                for seat, region in self.player_info.items()
            },
            "ui": self.ui,
        }


@dataclass(slots=True)
class TileObservation:
    tile: str
    confidence: float
    region_id: str
    bbox: Region | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileObservation":
        return cls(
            tile=str(data.get("tile", "unknown")),
            confidence=float(data.get("confidence", 0.0)),
            region_id=str(data.get("region_id", "")),
            bbox=Region.from_dict(data.get("bbox")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile": self.tile,
            "confidence": self.confidence,
            "region_id": self.region_id,
            "bbox": self.bbox.to_dict() if self.bbox else None,
        }


@dataclass(slots=True)
class GameState:
    missing_suit: str | None = None
    hand: list[str] = field(default_factory=list)
    hand_display: list[str] = field(default_factory=list)
    drawn_tile: str | None = None
    self_melds: list[list[str]] = field(default_factory=list)
    opponent_discards: dict[str, list[str]] = field(
        default_factory=lambda: {"left": [], "top": [], "right": []}
    )
    opponent_melds: dict[str, list[list[str]]] = field(
        default_factory=lambda: {"left": [], "top": [], "right": []}
    )
    visible_tiles: list[str] = field(default_factory=list)
    recognition_confidence: float = 1.0
    uncertain_tiles: list[TileObservation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        hand = normalize_tiles(data.get("hand", []))
        hand_display = [
            "X" if str(tile).strip().upper() == "X" else normalize_tiles([tile])[0]
            for tile in data.get("hand_display", hand)
        ]
        return cls(
            missing_suit=normalize_suit(data.get("missing_suit")),
            hand=hand,
            hand_display=hand_display,
            drawn_tile=(
                normalize_tiles([data["drawn_tile"]])[0]
                if data.get("drawn_tile")
                else None
            ),
            self_melds=[normalize_tiles(meld) for meld in data.get("self_melds", [])],
            opponent_discards={
                seat: normalize_tiles(tiles)
                for seat, tiles in data.get("opponent_discards", {}).items()
            }
            or {"left": [], "top": [], "right": []},
            opponent_melds={
                seat: [normalize_tiles(meld) for meld in melds]
                for seat, melds in data.get("opponent_melds", {}).items()
            }
            or {"left": [], "top": [], "right": []},
            visible_tiles=normalize_tiles(data.get("visible_tiles", [])),
            recognition_confidence=float(data.get("recognition_confidence", 1.0)),
            uncertain_tiles=[
                TileObservation.from_dict(tile)
                for tile in data.get("uncertain_tiles", [])
            ],
        )

    def all_hand_tiles(self) -> list[str]:
        tiles = list(self.hand)
        if self.drawn_tile:
            tiles.append(self.drawn_tile)
        return normalize_tiles(tiles)

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_suit": self.missing_suit,
            "hand": self.hand,
            "hand_display": self.hand_display or self.hand,
            "drawn_tile": self.drawn_tile,
            "self_melds": self.self_melds,
            "opponent_discards": self.opponent_discards,
            "opponent_melds": self.opponent_melds,
            "visible_tiles": self.visible_tiles,
            "recognition_confidence": self.recognition_confidence,
            "uncertain_tiles": [tile.to_dict() for tile in self.uncertain_tiles],
        }


@dataclass(slots=True)
class RecommendationResult:
    recommended_discard: str | None
    alternatives: list[str]
    route: list[str]
    reason: str
    risk_notes: list[str]
    confidence: float
    discard_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
