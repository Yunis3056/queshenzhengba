"""副露（碰/杠）后恢复出牌建议的回归测试。

对应 docs/superpowers/specs/2026-06-24-furo-discard-recovery-design.md（P1 最小修复）。
"""

from __future__ import annotations

import unittest

from queshen_agent.models import GameState, expected_hand_counts
from queshen_agent.shanten import best_shanten, standard_shanten
from queshen_agent.strategy import analyze_routes, recommend_discard


class ExpectedHandCountsTest(unittest.TestCase):
    def test_no_meld_is_backward_compatible(self) -> None:
        self.assertEqual(expected_hand_counts(0), (13, 14))

    def test_each_meld_subtracts_three(self) -> None:
        self.assertEqual(expected_hand_counts(1), (10, 11))
        self.assertEqual(expected_hand_counts(4), (1, 2))


class ShantenMeldsTest(unittest.TestCase):
    def test_peng_one_group_complete_hand_is_win(self) -> None:
        # 碰 5m 一组 + 暗手 3 面子 + 将 → 和牌
        dark = ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "9p", "9p"]
        self.assertEqual(standard_shanten(dark, melds_done=1), -1)
        self.assertEqual(best_shanten(dark, melds_done=1), -1)

    def test_peng_one_group_tenpai(self) -> None:
        # 碰一组 + 暗手 2 面子 + 将 + 一个两面搭子 → 听牌
        dark = ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9p", "9p"]
        self.assertEqual(standard_shanten(dark, melds_done=1), 0)

    def test_jingou_diao_tenpai_and_win(self) -> None:
        # 金钩钓：4 组副露 + 暗手单钓
        self.assertEqual(standard_shanten(["5m"], melds_done=4), 0)
        self.assertEqual(standard_shanten(["5m", "5m"], melds_done=4), -1)

    def test_f0_unchanged(self) -> None:
        tiles = ["1m", "2m", "3m", "2p", "3p", "4p", "5s", "6s", "7s", "7m", "7m", "7m", "9s", "9s"]
        self.assertEqual(standard_shanten(tiles), -1)


class StrategyFuroTest(unittest.TestCase):
    def test_peng_discard_state_gives_recommendation(self) -> None:
        # 碰一组（11 张暗手 = 14 等价的待打态）应给出出牌建议，而非 hand_count_unstable。
        state = GameState.from_dict(
            {
                "hand": ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "9p", "2p"],
                "self_melds": [["5m", "5m", "5m"]],
            }
        )

        result = recommend_discard(state)

        self.assertIsNotNone(result.recommended_discard)
        self.assertNotIn("hand_count_unstable", result.risk_notes)

    def test_seven_pairs_route_excluded_with_meld(self) -> None:
        # 对子很多但有副露 → 七对系不门清，路线应被排除。
        state = GameState.from_dict(
            {
                "hand": ["1m", "1m", "2m", "2m", "3m", "3m", "5p", "5p", "7p", "7p", "9s"],
                "self_melds": [["8s", "8s", "8s"]],
            }
        )

        routes = analyze_routes(state)

        self.assertNotIn("七对路线", routes)
        self.assertNotIn("龙七对路线", routes)
        self.assertNotIn("将七对路线", routes)

    def test_draw_animation_count_mismatch_stays_unstable(self) -> None:
        # 补摸/动画中间态：暗手张数与 expected_hand_counts(1)=(10,11) 不符 → 安全等待下一帧。
        state = GameState.from_dict(
            {
                "hand": ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "9p", "2p", "3p"],
                "self_melds": [["5m", "5m", "5m"]],
            }
        )

        result = recommend_discard(state)

        self.assertIsNone(result.recommended_discard)
        self.assertIn("hand_count_unstable", result.risk_notes)


if __name__ == "__main__":
    unittest.main()
