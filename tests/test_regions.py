from __future__ import annotations

import unittest

from queshen_agent.models import Region
from queshen_agent.recognition import _relative_region, ensure_template_dirs


class RegionTest(unittest.TestCase):
    def test_relative_region_converts_screen_coords_to_capture_coords(self) -> None:
        base = Region(100, 200, 800, 600)
        child = Region(150, 260, 300, 80)
        relative = _relative_region(child, base)

        self.assertIsNotNone(relative)
        assert relative is not None
        self.assertEqual(relative.x, 50)
        self.assertEqual(relative.y, 60)
        self.assertEqual(relative.width, 300)
        self.assertEqual(relative.height, 80)

    def test_template_dirs_can_be_created(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            paths = ensure_template_dirs(Path(tmp))
            self.assertEqual(len(paths), 27)
            self.assertTrue((Path(tmp) / "1m").exists())
            self.assertTrue((Path(tmp) / "9s").exists())


if __name__ == "__main__":
    unittest.main()
