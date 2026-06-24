from __future__ import annotations

from collections import Counter

from .models import GameState, RecommendationResult, expected_hand_counts
from .rules import RuleSet
from .shanten import best_shanten, seven_pairs_shanten, standard_shanten
from .tile import (
    counts_by_suit,
    counts_by_tile,
    matches_missing_suit,
    normalize_suit,
    sort_tiles,
    suit_label,
    tile_label,
    tile_rank,
    tile_suit,
)


def recommend_discard(game_state: GameState, rules: RuleSet | None = None) -> RecommendationResult:
    if any(tile == "X" for tile in game_state.hand_display):
        return RecommendationResult(
            recommended_discard=None,
            alternatives=[],
            route=[],
            reason="手牌里有无法确认的牌，已用 X 标出；先不要根据猜测出牌。",
            risk_notes=["hand_has_unknown_tiles"],
            confidence=0.0,
        )

    tiles = sort_tiles(game_state.all_hand_tiles())
    if not tiles:
        return RecommendationResult(
            recommended_discard=None,
            alternatives=[],
            route=[],
            reason="没有识别到手牌，先重新截图或手动修正牌面。",
            risk_notes=["hand_empty"],
            confidence=0.0,
        )
    if len(tiles) not in expected_hand_counts(game_state.meld_count):
        expected_text = "/".join(str(count) for count in expected_hand_counts(game_state.meld_count))
        return RecommendationResult(
            recommended_discard=None,
            alternatives=[],
            route=[],
            reason=f"当前识别到 {len(tiles)} 张暗手牌，不是完整的 {expected_text} 张（已计入 {game_state.meld_count} 组副露），可能处在出牌动画、补摸、胡牌后或截图遮挡中，先等待下一帧。",
            risk_notes=["hand_count_unstable"],
            confidence=0.0,
        )

    risk_notes: list[str] = []
    if game_state.recognition_confidence < 0.75:
        risk_notes.append("识别置信度偏低，建议先确认高亮牌。")
    if game_state.uncertain_tiles:
        risk_notes.append("存在未确认牌，请优先修正后再采纳建议。")

    routes = analyze_routes(game_state)
    missing_choice = recommend_missing_suit(game_state)
    if game_state.missing_suit is None and missing_choice is not None:
        suit, reason = missing_choice
        routes = [f"建议定缺{suit_label(suit)}", *routes]
        risk_notes.append(reason)
    discard_scores = {
        tile: _score_discard(tile, tiles, game_state)
        for tile in sorted(set(tiles), key=tiles.index)
    }

    missing_suit = normalize_suit(game_state.missing_suit)
    missing_tiles = [tile for tile in discard_scores if matches_missing_suit(tile, missing_suit)]
    if missing_tiles:
        candidate_scores = {tile: discard_scores[tile] + 10000 for tile in missing_tiles}
        ordered = _ordered_scores(candidate_scores)
        recommended = ordered[0]
        alternatives = ordered[1:3]
        reason = (
            f"你定缺{suit_label(missing_suit)}，手里还有缺门牌。"
            f"按规则摸到/持有缺门要先打，所以推荐打{tile_label(recommended)}。"
        )
        confidence = min(0.99, max(0.1, game_state.recognition_confidence))
        return RecommendationResult(
            recommended_discard=recommended,
            alternatives=alternatives,
            route=["先打缺门", *[route for route in routes if route != "先打缺门"]],
            reason=reason,
            risk_notes=risk_notes,
            confidence=confidence,
            discard_scores={tile: round(score, 3) for tile, score in discard_scores.items()},
        )

    ordered = _ordered_scores(discard_scores)
    recommended = ordered[0]
    alternatives = ordered[1:3]
    reason = _build_reason(recommended, tiles, game_state, routes)
    confidence = min(0.96, max(0.1, game_state.recognition_confidence))
    return RecommendationResult(
        recommended_discard=recommended,
        alternatives=alternatives,
        route=routes,
        reason=reason,
        risk_notes=risk_notes,
        confidence=confidence,
        discard_scores={tile: round(score, 3) for tile, score in discard_scores.items()},
    )


def recommend_missing_suit(game_state: GameState) -> tuple[str, str] | None:
    if game_state.missing_suit is not None:
        return None
    tiles = sort_tiles(game_state.all_hand_tiles())
    if len(tiles) not in expected_hand_counts(game_state.meld_count):
        return None

    suit_tiles = {suit: [tile for tile in tiles if tile_suit(tile) == suit] for suit in ("m", "p", "s")}
    scores = {suit: _missing_suit_score(items) for suit, items in suit_tiles.items()}
    recommended = min(scores, key=lambda suit: (scores[suit], len(suit_tiles[suit])))
    counts_text = "、".join(f"{suit_label(suit)}{len(suit_tiles[suit])}张" for suit in ("m", "p", "s"))
    reason = f"尚未读到定缺标记；按当前手牌分布（{counts_text}）建议定缺{suit_label(recommended)}。"
    return recommended, reason


def analyze_routes(game_state: GameState) -> list[str]:
    tiles = sort_tiles(game_state.all_hand_tiles())
    routes: list[str] = []

    missing_suit = normalize_suit(game_state.missing_suit)
    if missing_suit and any(matches_missing_suit(tile, missing_suit) for tile in tiles):
        routes.append("先打缺门")

    tile_counts = counts_by_tile(tiles)
    suit_counts = counts_by_suit(tiles)
    pair_units = sum(count // 2 for count in tile_counts.values())
    quad_count = sum(1 for count in tile_counts.values() if count == 4)
    jiang_count = sum(count for tile, count in tile_counts.items() if tile_rank(tile) in (2, 5, 8))
    dominant_suit, dominant_count = suit_counts.most_common(1)[0] if suit_counts else (None, 0)

    if not game_state.self_melds and seven_pairs_shanten(tiles) <= 2:
        if quad_count >= 1:
            routes.append("龙七对路线")
        else:
            routes.append("七对路线")

    if jiang_count >= 9:
        if pair_units >= 5 and not game_state.self_melds:
            routes.append("将七对路线")
        else:
            routes.append("将对路线")

    if dominant_suit and dominant_count >= 9:
        routes.append(f"清一色路线（{suit_label(dominant_suit)}）")

    if _triplet_like_count(tile_counts) >= 3:
        routes.append("碰碰胡路线")

    standard = standard_shanten(tiles, game_state.meld_count)
    # 有副露时七对路线不适用，用标准型替代以免污染听牌判断。
    seven = seven_pairs_shanten(tiles) if not game_state.self_melds else standard
    if min(standard, seven) <= 1:
        routes.append("接近听牌")
    elif standard <= 3:
        routes.append("平胡牌效率")

    return _dedupe(routes) or ["按牌效率整理"]


def _missing_suit_score(tiles: list[str]) -> float:
    if not tiles:
        return -100.0
    counts = counts_by_tile(tiles)
    ranks = sorted(tile_rank(tile) for tile in tiles)
    score = len(tiles) * 100.0
    score += sum((count - 1) * 35 for count in counts.values() if count >= 2)
    for rank in ranks:
        if rank in (2, 5, 8):
            score += 8
    rank_set = set(ranks)
    for rank in rank_set:
        if rank + 1 in rank_set:
            score += 20
        if rank + 2 in rank_set:
            score += 10
    return score


def _score_discard(tile: str, tiles: list[str], game_state: GameState) -> float:
    remaining = list(tiles)
    remaining.remove(tile)
    counts = counts_by_tile(tiles)
    suit_counts = counts_by_suit(tiles)
    visible = _visible_counts(game_state)
    melds_done = game_state.meld_count
    score = 0.0

    # Lower shanten after discard is better.
    # 注（P6）：13/等待态手牌没有摸牌，这里算的是"弃一张后"的向听，
    # 仅作保留价值启发式参考、不等于催打；待打态(14/上限张)才是真正要出的牌。
    score += -best_shanten(remaining, melds_done) * 120
    score += -standard_shanten(remaining, melds_done) * 18
    if not game_state.self_melds:
        score += -seven_pairs_shanten(remaining) * 16

    count = counts[tile]
    rank = tile_rank(tile)
    suit = tile_suit(tile)
    same_suit_tiles = [other for other in tiles if tile_suit(other) == suit and other != tile]
    neighbor_count = sum(1 for other in same_suit_tiles if abs(tile_rank(other) - rank) in (1, 2))

    if count == 1:
        score += 18
        if neighbor_count == 0:
            score += 18
        elif neighbor_count == 1:
            score += 7
    elif count == 2:
        score -= 30
    elif count == 3:
        score -= 42
    elif count == 4:
        score -= 25

    if rank in (1, 9):
        score += 8
        if neighbor_count == 0:
            score += 8
    elif rank in (2, 8):
        score += 2
    else:
        score -= 3

    pair_units = sum(value // 2 for value in counts.values())
    if not game_state.self_melds and pair_units >= 5 and count >= 2:
        score -= 35

    jiang_count = sum(value for item, value in counts.items() if tile_rank(item) in (2, 5, 8))
    if jiang_count >= 9 and rank in (2, 5, 8):
        score -= 22

    if suit_counts:
        dominant_suit, dominant_count = suit_counts.most_common(1)[0]
        if dominant_count >= 9 and suit != dominant_suit:
            score += 24
        elif dominant_count >= 9 and suit == dominant_suit:
            score -= 14

    # P3：胡牌≤2门花色。未定缺且三门均布的早期，轻微倾向打掉最弱门以主动收敛
    # （定缺生效后由 +10000 缺门机制接管，这里只补未定缺的早期空窗）。
    if game_state.missing_suit is None:
        present_suits = [item for item, value in suit_counts.items() if value > 0]
        if len(present_suits) >= 3:
            weakest_suit = min(present_suits, key=lambda item: (suit_counts[item], item))
            if suit == weakest_suit:
                score += 10

    visible_count = visible[tile]
    if visible_count >= 3:
        score += 12

    wait_tiles = _useful_neighbor_tiles(tile)
    dead_waits = sum(1 for wait in wait_tiles if visible[wait] >= 4)
    thin_waits = sum(1 for wait in wait_tiles if visible[wait] >= 3)
    if dead_waits:
        score += dead_waits * 10
    if thin_waits:
        score += thin_waits * 4

    if count == 1 and neighbor_count == 0 and visible_count >= 2:
        score += 8
    if count >= 2 and visible_count >= 2:
        score += 6

    return score


def _build_reason(recommended: str, tiles: list[str], game_state: GameState, routes: list[str]) -> str:
    counts = counts_by_tile(tiles)
    rank = tile_rank(recommended)
    suit = tile_suit(recommended)
    neighbors = [
        tile
        for tile in tiles
        if tile != recommended and tile_suit(tile) == suit and abs(tile_rank(tile) - rank) in (1, 2)
    ]
    route_text = "、".join(routes[:2])

    if counts[recommended] == 1 and not neighbors:
        return f"推荐打{tile_label(recommended)}。它是孤张，和周围牌连接少，打掉后更容易保留{route_text}。"
    if counts[recommended] == 1 and rank in (1, 9):
        return f"推荐打{tile_label(recommended)}。它是边张单牌，进张面较窄，目前保留价值偏低。"
    if "清一色" in "".join(routes):
        dominant = counts_by_suit(tiles).most_common(1)[0][0]
        if tile_suit(recommended) != dominant:
            return f"推荐打{tile_label(recommended)}。当前更像清一色路线，这张不是主花色，先清掉更顺。"
    if any(route in routes for route in ("七对路线", "龙七对路线", "将七对路线")) and counts[recommended] == 1:
        return f"推荐打{tile_label(recommended)}。对子路线下单张价值低，优先保留对子和四张相同牌。"
    return f"推荐打{tile_label(recommended)}。综合缺门、向听数、搭子价值和番型潜力后，这张牌的保留价值最低。"


def _ordered_scores(scores: dict[str, float]) -> list[str]:
    return [
        tile
        for tile, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], tile_rank(item[0]), tile_suit(item[0])),
        )
    ]


def _triplet_like_count(counts: Counter[str]) -> int:
    return sum(1 for count in counts.values() if count >= 3)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _visible_counts(game_state: GameState) -> Counter[str]:
    visible = Counter(game_state.visible_tiles)
    for discards in game_state.opponent_discards.values():
        visible.update(discards)
    for melds in game_state.opponent_melds.values():
        for meld in melds:
            visible.update(meld)
    return visible


def _useful_neighbor_tiles(tile: str) -> list[str]:
    rank = tile_rank(tile)
    suit = tile_suit(tile)
    candidates = []
    for other_rank in (rank - 2, rank - 1, rank + 1, rank + 2):
        if 1 <= other_rank <= 9:
            candidates.append(f"{other_rank}{suit}")
    return candidates
