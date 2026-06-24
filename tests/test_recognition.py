from __future__ import annotations

import unittest

from queshen_agent.recognition import RecognizerConfig, _split_wide_boxes


class RecognitionTest(unittest.TestCase):
    def test_wide_connected_hand_box_splits_into_tiles(self) -> None:
        boxes = [(14, 20, 803, 84)]

        split = _split_wide_boxes(boxes, RecognizerConfig())

        self.assertEqual(len(split), 13)
        self.assertEqual(split[0][0], 14)
        self.assertGreaterEqual(split[-1][0] + split[-1][2], 14 + 803 - 1)

    def test_expected_hand_counts_include_draw_state(self) -> None:
        config = RecognizerConfig()

        self.assertEqual(config.expected_hand_counts, (13, 14))


if __name__ == "__main__":
    unittest.main()
