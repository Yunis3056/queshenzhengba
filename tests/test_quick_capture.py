from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.quick_capture as quick_capture


class QuickCaptureConfigTest(unittest.TestCase):
    def test_old_config_loads_with_new_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "quick_capture.json"
            config_path.write_text(
                json.dumps(
                    {
                        "x": 10,
                        "y": 20,
                        "width": 300,
                        "height": 200,
                        "output_dir": "watch/inbox",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(quick_capture, "CONFIG_PATH", config_path):
                config = quick_capture.load_config()

            self.assertEqual(config.x, 10)
            self.assertEqual(config.output_dir, "watch/inbox")
            self.assertEqual(config.frame_interval_seconds, 1.0)
            self.assertEqual(config.latest_frame_name, "latest.png")
            self.assertTrue(config.keep_frame_history)
            self.assertFalse(config.collect_round_frames)
            self.assertTrue(config.round_dir.endswith("rounds"))

    def test_legacy_output_dir_is_migrated_to_current_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "quick_capture.json"
            config_path.write_text(
                json.dumps(
                    {
                        "output_dir": "C:\\Users\\Yunis\\Documents\\Codex\\2026-06-22\\ni\\watch\\inbox",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(quick_capture, "CONFIG_PATH", config_path):
                config = quick_capture.load_config()

            self.assertEqual(config.output_dir, str(quick_capture.WATCH_INBOX))

    def test_logical_region_scales_to_capture_pixels(self) -> None:
        app = object.__new__(quick_capture.QuickCaptureApp)
        app.screen_scale_x = 1.5
        app.screen_scale_y = 2.0

        self.assertEqual(
            app._logical_to_capture_region((10, 20, 100, 50)),
            (15, 40, 150, 100),
        )

    def test_relative_paths_resolve_under_project_root(self) -> None:
        result = quick_capture.resolve_project_path("watch/frames")

        self.assertEqual(result, quick_capture.ROOT / "watch" / "frames")


if __name__ == "__main__":
    unittest.main()
