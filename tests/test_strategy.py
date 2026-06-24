from __future__ import annotations

import unittest

from queshen_agent.models import GameState
from queshen_agent.strategy import analyze_routes, recommend_discard, recommend_missing_suit


class StrategyTest(unittest.TestCase):
    def test_missing_suit_is_forced_first(self) -> None:
        state = GameState.from_dict(
            {
                "missing_suit": "tong",
                "hand": ["1m", "2m", "3m", "5m", "5m", "8m", "8m", "2s", "3s", "4s", "6s", "7s", "9p"],
            }
        )

        result = recommend_discard(state)

        self.assertEqual(result.recommended_discard, "9p")
        self.assertIn("先打缺门", result.route)
        self.assertIn("定缺筒", result.reason)

    def test_seven_pairs_route_is_detected(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["1m", "1m", "2m", "2m", "3m", "3m", "5p", "5p", "7p", "7p", "8s", "8s", "9s"],
            }
        )

        routes = analyze_routes(state)

        self.assertIn("七对路线", routes)

    def test_jiang_route_is_detected(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["2m", "2m", "5m", "5m", "8m", "8m", "2p", "2p", "5p", "5p", "8s", "8s", "2s"],
            }
        )

        routes = analyze_routes(state)

        self.assertTrue(any("将" in route for route in routes))

    def test_recommendation_returns_alternative_and_scores(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["1m", "2m", "3m", "5m", "6m", "8m", "2s", "3s", "4s", "7s", "7s", "9p", "9p"],
                "recognition_confidence": 0.88,
            }
        )

        result = recommend_discard(state)

        self.assertIsNotNone(result.recommended_discard)
        self.assertTrue(result.discard_scores)
        self.assertGreater(result.confidence, 0.8)

    def test_incomplete_hand_does_not_return_discard(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["1m", "2m", "3m", "5m", "6m", "8m", "2s", "3s", "4s", "7s"],
                "recognition_confidence": 0.9,
            }
        )

        result = recommend_discard(state)

        self.assertIsNone(result.recommended_discard)
        self.assertIn("hand_count_unstable", result.risk_notes)

    def test_unknown_display_tile_does_not_return_discard(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["1m", "2m", "3m", "5m", "6m", "8m", "2s", "3s", "4s", "7s", "7s", "8s", "9s"],
                "hand_display": ["1m", "2m", "3m", "5m", "6m", "8m", "2s", "3s", "4s", "7s", "7s", "8s", "X"],
                "recognition_confidence": 0.0,
            }
        )

        result = recommend_discard(state)

        self.assertIsNone(result.recommended_discard)
        self.assertIn("hand_has_unknown_tiles", result.risk_notes)

    def test_recommend_missing_suit_uses_weakest_suit(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["3m", "7m", "1p", "2p", "3p", "5p", "5p", "6p", "7p", "2s", "3s", "4s", "8s"],
                "recognition_confidence": 0.9,
            }
        )

        result = recommend_missing_suit(state)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "m")

    def test_missing_suit_suggestion_is_included_before_dingque(self) -> None:
        state = GameState.from_dict(
            {
                "hand": ["3m", "7m", "1p", "2p", "3p", "5p", "5p", "6p", "7p", "2s", "3s", "4s", "8s"],
                "recognition_confidence": 0.9,
            }
        )

        result = recommend_discard(state)

        self.assertTrue(result.route[0].startswith("建议定缺"))

    def test_visible_tiles_increase_discard_score_for_exhausted_waits(self) -> None:
        base = GameState.from_dict(
            {
                "hand": ["3m", "5m", "7m", "7m", "2p", "3p", "4p", "5p", "6p", "2s", "3s", "4s", "8s"],
                "recognition_confidence": 1.0,
            }
        )
        visible = GameState.from_dict(
            {
                "hand": ["3m", "5m", "7m", "7m", "2p", "3p", "4p", "5p", "6p", "2s", "3s", "4s", "8s"],
                "opponent_discards": {"left": ["4m", "4m", "4m", "4m"], "top": [], "right": []},
                "recognition_confidence": 1.0,
            }
        )

        base_result = recommend_discard(base)
        visible_result = recommend_discard(visible)

        self.assertGreater(visible_result.discard_scores["3m"], base_result.discard_scores["3m"])


if __name__ == "__main__":
    unittest.main()
