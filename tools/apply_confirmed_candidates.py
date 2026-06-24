from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy confirmed candidate crops into template folders.")
    parser.add_argument("candidate_dir", type=Path)
    args = parser.parse_args()

    assignments = {
        "hand_01_unknown.png": "1m",
        "hand_02_unknown.png": "7m",
        "hand_03_unknown.png": "8m",
        "hand_04_unknown.png": "9m",
        "hand_05_unknown.png": "1p",
        "hand_06_unknown.png": "2p",
        "hand_07_unknown.png": "2p",
        "hand_09_unknown.png": "8p",
        "hand_10_unknown.png": "9p",
    }
    for name, tile in assignments.items():
        source = args.candidate_dir / name
        if not source.exists():
            raise FileNotFoundError(source)
        target_dir = Path("samples") / "templates" / tile
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"confirmed_20260623_003849_{name}"
        shutil.copy2(source, target)
        print(f"{source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
