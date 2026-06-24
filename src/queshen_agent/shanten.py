from __future__ import annotations

from functools import lru_cache

from .tile import counts_to_27


def seven_pairs_shanten(tiles: list[str]) -> int:
    counts = counts_to_27(tiles)
    # count//2：一组杠(4张)按"两对"计入七对结构——这是龙七对规则的本意（1组杠=两对），
    # 故 4+4+4+2 判为七对和了(-1)，并非 bug。勿改成 count==2 才算一对。
    pair_units = sum(count // 2 for count in counts)
    if pair_units >= 7:
        return -1
    return 6 - pair_units


def standard_shanten(tiles: list[str], melds_done: int = 0) -> int:
    """标准型向听。

    `melds_done`=已锁定的副露（碰/杠）组数，每组折算为一个已完成面子：
    手牌内只需再凑 `meld_budget = 4 - melds_done` 个面子。melds_done=0 时退化为原式
    `8 - 2*melds - taatsu - has_pair`，向后兼容。
    """
    counts = counts_to_27(tiles)
    meld_budget = 4 - melds_done
    best = 2 * meld_budget

    pair_choices = [None]
    pair_choices.extend(index for index, count in enumerate(counts) if count >= 2)

    for pair_index in pair_choices:
        mutable = list(counts)
        has_pair = 0
        if pair_index is not None:
            mutable[pair_index] -= 2
            has_pair = 1
        melds, taatsu = _best_meld_taatsu(tuple(mutable))
        melds = min(melds, meld_budget)
        taatsu = min(taatsu, meld_budget - melds)
        shanten = 2 * meld_budget - (2 * melds) - taatsu - has_pair
        best = min(best, shanten)
    return best


def best_shanten(tiles: list[str], melds_done: int = 0) -> int:
    # 七对系要求门清，副露后不适用，故有副露时只看标准型。
    if melds_done > 0:
        return standard_shanten(tiles, melds_done)
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
