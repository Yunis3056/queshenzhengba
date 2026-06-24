from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from queshen_agent.models import Region, RegionConfig
from queshen_agent.template_collection import (
    collect_template_candidates,
    find_latest_screenshot,
    region_for_key,
    rotation_for_region_key,
    save_template_crop,
    template_region_keys,
)


class TemplateCollectionTest(unittest.TestCase):
    def test_region_for_key_converts_to_screenshot_relative_coordinates(self) -> None:
        config = RegionConfig(
            game_area=Region(100, 200, 1280, 720),
            hand=Region(345, 735, 770, 170),
            opponent_discards={"left": Region(460, 360, 180, 245)},
        )

        hand = region_for_key(config, "hand")
        left_discards = region_for_key(config, "opponent_discards.left")

        self.assertEqual(hand, Region(245, 535, 770, 170))
        self.assertEqual(left_discards, Region(360, 160, 180, 245))

    def test_save_template_crop_writes_to_tile_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "screen.png"
            Image.new("RGB", (100, 80), "white").save(image_path)

            output = save_template_crop(
                image_path,
                Region(10, 12, 20, 24),
                "1m",
                root / "templates",
            )

            self.assertEqual(output.parent.name, "1m")
            self.assertTrue(output.exists())
            with Image.open(output) as image:
                self.assertEqual(image.size, (20, 24))

    def test_template_region_keys_can_include_table_regions(self) -> None:
        keys = template_region_keys(include_opponents=True)

        self.assertIn("opponent_discards.left", keys)
        self.assertIn("opponent_discards.top", keys)
        self.assertIn("opponent_discards.right", keys)
        self.assertIn("center_discards", keys)

    def test_rotation_for_region_key_normalizes_table_seats(self) -> None:
        self.assertEqual(rotation_for_region_key("opponent_discards.left"), 90)
        self.assertEqual(rotation_for_region_key("opponent_discards.top"), 180)
        self.assertEqual(rotation_for_region_key("opponent_discards.right"), -90)
        self.assertEqual(rotation_for_region_key("hand"), 0)

    def test_collect_template_candidates_saves_region_preview_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "screen.png"
            Image.new("RGB", (1280, 720), "#20242d").save(image_path)
            config = RegionConfig(
                game_area=Region(0, 0, 1280, 720),
                hand=Region(245, 535, 100, 80),
            )

            export = collect_template_candidates(
                image_path,
                config,
                root / "candidates",
                region_keys=("hand",),
            )

            self.assertTrue(export.manifest_path.exists())
            self.assertTrue(export.region_crops["hand"].exists())
            self.assertTrue(export.previews["hand"].exists())

    def test_find_latest_screenshot_ignores_non_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "older.png"
            newer = root / "newer.jpg"
            text = root / "note.txt"
            Image.new("RGB", (8, 8), "white").save(older)
            Image.new("RGB", (8, 8), "black").save(newer)
            text.write_text("ignore me", encoding="utf-8")

            result = find_latest_screenshot([root])

            self.assertEqual(result, newer)


if __name__ == "__main__":
    unittest.main()
