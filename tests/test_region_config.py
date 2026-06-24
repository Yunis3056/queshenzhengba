from __future__ import annotations

import unittest

from queshen_agent.layout_profiles import load_profile_1280x720_v2


class RegionConfigTest(unittest.TestCase):
    def test_v2_profile_loads_new_regions(self) -> None:
        config = load_profile_1280x720_v2()

        self.assertIsNotNone(config.drawn_tile)
        self.assertIsNotNone(config.turn_timer)
        self.assertIsNotNone(config.center_discards)
        self.assertIsNotNone(config.self_melds)
        assert config.self_melds is not None
        self.assertGreaterEqual(config.self_melds.width, 600)


if __name__ == "__main__":
    unittest.main()
