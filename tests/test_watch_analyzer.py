from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from queshen_agent.watch_analyzer import (
    _file_signature,
    _write_latest_result,
    _write_latest_text,
    load_frame_analyzer_config,
)
from queshen_agent.models import GameState, RecommendationResult, TileObservation


class WatchAnalyzerTest(unittest.TestCase):
    def test_frame_analyzer_config_loads_defaults_and_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "frame_analyzer.json"
            config_path.write_text(
                json.dumps(
                    {
                        "latest_frame_path": "watch/frames/custom.png",
                        "poll_seconds": 0.1,
                        "write_latest_result": False,
                    }
                ),
                encoding="utf-8",
            )

            config = load_frame_analyzer_config(config_path)

            self.assertTrue(str(config.latest_frame_path).endswith("watch\\frames\\custom.png") or str(config.latest_frame_path).endswith("watch/frames/custom.png"))
            self.assertEqual(config.poll_seconds, 0.1)
            self.assertFalse(config.write_latest_result)
            self.assertFalse(config.keep_result_history)
            self.assertTrue(str(config.latest_text_path).endswith("watch\\results\\latest_result.txt") or str(config.latest_text_path).endswith("watch/results/latest_result.txt"))
            self.assertTrue(str(config.results_dir).endswith("watch\\results") or str(config.results_dir).endswith("watch/results"))

    def test_file_signature_changes_when_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.png"
            self.assertIsNone(_file_signature(path))

            path.write_bytes(b"one")
            first = _file_signature(path)
            path.write_bytes(b"two-two")
            second = _file_signature(path)

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertNotEqual(first, second)

    def test_write_latest_result_replaces_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "latest_result.json"
            target.write_text('{"old": true}', encoding="utf-8")
            state = GameState(hand=["1m"])
            recommendation = RecommendationResult(
                recommended_discard="1m",
                alternatives=[],
                route=[],
                reason="test",
                risk_notes=[],
                confidence=1.0,
            )

            _write_latest_result(root / "latest.png", state, recommendation, target)

            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["game_state"]["hand"], ["1m"])
            self.assertEqual(payload["recommendation"]["recommended_discard"], "1m")

    def test_write_latest_text_is_human_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "latest_result.txt"
            state = GameState(hand=["1m"], missing_suit="m", recognition_confidence=0.8)
            recommendation = RecommendationResult(
                recommended_discard="1m",
                alternatives=["2m"],
                route=[],
                reason="test reason",
                risk_notes=[],
                confidence=0.9,
            )

            _write_latest_text(root / "latest.png", state, recommendation, target)

            text = target.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("建议打：1万\n"))
            self.assertIn("建议打：1万", text)
            self.assertIn("原因：test reason", text)
            self.assertIn("定缺：万", text)

    def test_write_latest_text_shows_unknown_tiles_as_x(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "latest_result.txt"
            state = GameState(
                hand=["1m", "7m"],
                hand_display=["1m", "X", "7m"],
                recognition_confidence=0.0,
                uncertain_tiles=[TileObservation(tile="5m", confidence=0.21, region_id="hand")],
            )
            recommendation = RecommendationResult(
                recommended_discard=None,
                alternatives=[],
                route=[],
                reason="unknown",
                risk_notes=["hand_has_unknown_tiles"],
                confidence=0.0,
            )

            _write_latest_text(root / "latest.png", state, recommendation, target)

            text = target.read_text(encoding="utf-8")
            self.assertIn("手牌：1万 X 7万", text)
            self.assertIn("未确认牌：1:5万(21%)", text)


if __name__ == "__main__":
    unittest.main()
