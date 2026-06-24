from __future__ import annotations

from functools import lru_cache

from .tile import counts_to_27


def seven_pairs_shanten(tiles: list[str]) -> int:
    counts = counts_to_27(tiles)
    pair_units = sum(count // 2 for count in counts)
    if pair_units >= 7:
        return -1
    return 6 - pair_units


def standard_shanten(tiles: list[str]) -> int:
    counts = counts_to_27(tiles)
    best = 8

    pair_choices = [None]
    pair_choices.extend(index for index, count in enumerate(counts) if count >= 2)

    for pair_index in pair_choices:
        mutable = list(counts)
        has_pair = 0
        if pair_index is not None:
            mutable[pair_index] -= 2
            has_pair = 1
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        taatsu = min(taatsu, 4 - melds)
        shanten = 8 - (2 * melds) - taatsu - has_pair
        best = min(best, shanten)
    return best


def best_shanten(tiles: list[str]) -> int:
    return min(standard_shanten(tiles), seven_pairs_shanten(tiles))


@lru_cache(maxsize=200000)
def _best_meld_taatsu(counts: tuple[int, ...]) -> tuple[int, int]:
    first = next((index for index, count in enumerate(counts) if count > 0), None)
    if first is None:
        return 0, 0

    best = (0, 0)

    def better(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
        score_a = a[0] * 2 + min(a[1], 4 - a[0])
        score_b = b[0] * 2 + min(b[1], 4 - b[0])
        if score_b > score_a:
            return b
        if score_b == score_a and b[0] > a[0]:
            return b
        return a

    mutable = list(counts)

    # Treat one tile as isolated.
    mutable[first] -= 1
    best = better(best, _best_meld_taatsu(tuple(mutable)))
    mutable[first] += 1

    # Triplet.
    if mutable[first] >= 3:
        mutable[first] -= 3
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        best = better(best, (melds + 1, taatsu))
        mutable[first] += 3

    suit_start = (first // 9) * 9
    rank_index = first % 9

    # Sequence.
    if rank_index <= 6 and mutable[first + 1] > 0 and mutable[first + 2] > 0:
        mutable[first] -= 1
        mutable[first + 1] -= 1
        mutable[first + 2] -= 1
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        best = better(best, (melds + 1, taatsu))
        mutable[first] += 1
        mutable[first + 1] += 1
        mutable[first + 2] += 1

    # Pair as incomplete set.
    if mutable[first] >= 2:
        mutable[first] -= 2
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        best = better(best, (melds, taatsu + 1))
        mutable[first] += 2

    # Two-sided/edge incomplete sequence.
    if rank_index <= 7 and first + 1 < suit_start + 9 and mutable[first + 1] > 0:
        mutable[first] -= 1
        mutable[first + 1] -= 1
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        best = better(best, (melds, taatsu + 1))
        mutable[first] += 1
        mutable[first + 1] += 1

    # Closed wait incomplete sequence.
    if rank_index <= 6 and first + 2 < suit_start + 9 and mutable[first + 2] > 0:
        mutable[first] -= 1
        mutable[first + 2] -= 1
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        best = better(best, (melds, taatsu + 1))
        mutable[first] += 1
        mutable[first + 2] += 1

    return best
