"""视觉路径人类可读文本格式化测试（P4：牌码与本地路径一致归一为中文标签）。"""

from __future__ import annotations

import unittest

from queshen_agent.vision_analyzer import _format_human_text


class VisionFormatTest(unittest.TestCase):
    def test_tile_codes_render_as_chinese_labels(self) -> None:
        payload = {
            "recommended_discard": "7m",
            "alternatives": ["3p", "9s"],
            "hand": ["1m", "2m", "3m"],
            "drawn_tile": "5p",
            "missing_suit": "p",
            "route": ["先打缺门"],
            "reason": "测试",
            "risk_notes": [],
            "confidence": 0.8,
        }

        text = _format_human_text(payload)

        self.assertIn("建议打：7万", text)
        self.assertIn("1万 2万 3万", text)
        self.assertIn("3筒、9条", text)
        self.assertIn("摸牌：5筒", text)
        self.assertIn("定缺：筒", text)

    def test_invalid_tile_code_falls_back_to_raw(self) -> None:
        payload = {
            "recommended_discard": "??",
            "alternatives": [],
            "hand": [],
            "drawn_tile": None,
            "missing_suit": None,
            "route": [],
            "reason": "",
            "risk_notes": [],
            "confidence": 0.0,
        }

        text = _format_human_text(payload)

        self.assertIn("建议打：??", text)
        self.assertIn("摸牌：无", text)
        self.assertIn("定缺：未知", text)


if __name__ == "__main__":
    unittest.main()
