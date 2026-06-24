from __future__ import annotations

from collections import Counter
from typing import Iterable


SUIT_TO_ID = {"m": "wan", "p": "tong", "s": "tiao"}
ID_TO_SUIT = {value: key for key, value in SUIT_TO_ID.items()}
SUIT_LABELS = {"m": "万", "p": "筒", "s": "条"}
ID_LABELS = {"wan": "万", "tong": "筒", "tiao": "条"}
ALL_TILES = [f"{rank}{suit}" for suit in ("m", "p", "s") for rank in range(1, 10)]
TILE_INDEX = {tile: index for index, tile in enumerate(ALL_TILES)}
INDEX_TILE = {index: tile for tile, index in TILE_INDEX.items()}


def normalize_suit(suit: str | None) -> str | None:
    if not suit:
        return None
    lowered = suit.strip().lower()
    aliases = {
        "m": "m",
        "wan": "m",
        "万": "m",
        "p": "p",
        "tong": "p",
        "筒": "p",
        "饼": "p",
        "s": "s",
        "tiao": "s",
        "条": "s",
        "索": "s",
    }
    return aliases.get(lowered)


def normalize_tile(tile: str) -> str:
    raw = tile.strip().lower()
    if len(raw) < 2:
        raise ValueError(f"Invalid tile: {tile!r}")
    rank_text = raw[:-1]
    suit_text = raw[-1]
    suit = normalize_suit(suit_text)
    if suit is None:
        raise ValueError(f"Invalid tile suit: {tile!r}")
    try:
        rank = int(rank_text)
    except ValueError as exc:
        raise ValueError(f"Invalid tile rank: {tile!r}") from exc
    if rank < 1 or rank > 9:
        raise ValueError(f"Invalid tile rank: {tile!r}")
    return f"{rank}{suit}"


def normalize_tiles(tiles: Iterable[str]) -> list[str]:
    return [normalize_tile(tile) for tile in tiles]


def tile_rank(tile: str) -> int:
    return int(normalize_tile(tile)[:-1])


def tile_suit(tile: str) -> str:
    return normalize_tile(tile)[-1]


def tile_suit_id(tile: str) -> str:
    return SUIT_TO_ID[tile_suit(tile)]


def tile_label(tile: str) -> str:
    normalized = normalize_tile(tile)
    return f"{int(normalized[:-1])}{SUIT_LABELS[normalized[-1]]}"


def suit_label(suit: str | None) -> str:
    normalized = normalize_suit(suit)
    if normalized is None:
        return "未知"
    return SUIT_LABELS[normalized]


def matches_missing_suit(tile: str, missing_suit: str | None) -> bool:
    normalized = normalize_suit(missing_suit)
    return normalized is not None and tile_suit(tile) == normalized


def counts_by_tile(tiles: Iterable[str]) -> Counter[str]:
    return Counter(normalize_tiles(tiles))


def counts_by_suit(tiles: Iterable[str]) -> Counter[str]:
    return Counter(tile_suit(tile) for tile in normalize_tiles(tiles))


def counts_to_27(tiles: Iterable[str]) -> tuple[int, ...]:
    counts = [0] * 27
    for tile in normalize_tiles(tiles):
        counts[TILE_INDEX[tile]] += 1
    return tuple(counts)


def sort_tiles(tiles: Iterable[str]) -> list[str]:
    return sorted(normalize_tiles(tiles), key=lambda tile: TILE_INDEX[tile])
