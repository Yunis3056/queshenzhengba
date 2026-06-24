from __future__ import annotations

import unittest

from queshen_agent.shanten import best_shanten, seven_pairs_shanten, standard_shanten


class ShantenTest(unittest.TestCase):
    def test_complete_standard_hand_is_negative_one(self) -> None:
        tiles = ["1m", "2m", "3m", "2p", "3p", "4p", "5s", "6s", "7s", "7m", "7m", "7m", "9s", "9s"]
        self.assertEqual(standard_shanten(tiles), -1)
        self.assertEqual(best_shanten(tiles), -1)

    def test_complete_seven_pairs_is_negative_one(self) -> None:
        tiles = ["1m", "1m", "2m", "2m", "3m", "3m", "5p", "5p", "7p", "7p", "8s", "8s", "9s", "9s"]
        self.assertEqual(seven_pairs_shanten(tiles), -1)
        self.assertEqual(best_shanten(tiles), -1)


if __name__ == "__main__":
    unittest.main()
