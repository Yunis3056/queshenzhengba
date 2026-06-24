from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import GameState
from .rules import load_rules
from .strategy import recommend_discard


def main() -> int:
    parser = argparse.ArgumentParser(description="Queshen Zhengba AI coach CLI.")
    parser.add_argument("--state", type=Path, help="Path to a GameState JSON file.")
    parser.add_argument("--hand", nargs="*", help="Hand tiles like 1m 2m 3m.")
    parser.add_argument("--missing-suit", help="Missing suit: m/p/s or wan/tong/tiao.")
    args = parser.parse_args()

    if args.state:
        with args.state.open("r", encoding="utf-8") as file:
            state = GameState.from_dict(json.load(file))
    else:
        state = GameState.from_dict(
            {
                "missing_suit": args.missing_suit,
                "hand": args.hand or [],
                "recognition_confidence": 1.0,
            }
        )

    result = recommend_discard(state, load_rules())
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
