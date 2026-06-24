from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import RULES_PATH


@dataclass(slots=True)
class FanPattern:
    id: str
    label_zh: str
    multiplier: int
    category: str
    description: str
    requirements: dict[str, Any]
    excludes: list[str]


class RuleSet:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.patterns = [
            FanPattern(
                id=item["id"],
                label_zh=item["label_zh"],
                multiplier=int(item["multiplier"]),
                category=item["category"],
                description=item["description"],
                requirements=dict(item.get("requirements", {})),
                excludes=list(item.get("excludes", [])),
            )
            for item in data.get("fan_patterns", [])
        ]
        self.pattern_by_id = {pattern.id: pattern for pattern in self.patterns}

    @property
    def can_chi(self) -> bool:
        return bool(self.data["tile_set"]["can_chi"])

    @property
    def can_peng(self) -> bool:
        return bool(self.data["tile_set"]["can_peng"])

    @property
    def can_gang(self) -> bool:
        return bool(self.data["tile_set"]["can_gang"])

    @property
    def max_win_suits(self) -> int:
        return int(self.data["round_rules"]["dingque"]["winning_hand_max_suit_count"])


def load_rules(path: Path = RULES_PATH) -> RuleSet:
    with path.open("r", encoding="utf-8") as file:
        return RuleSet(json.load(file))
