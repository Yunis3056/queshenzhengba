from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import GameState, RecommendationResult
from .paths import RUNS_DIR


def save_run_record(
    screenshot_path: Path | None,
    state: GameState,
    recommendation: RecommendationResult,
    output_dir: Path = RUNS_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = output_dir / f"run_{timestamp}.json"
    payload = {
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "game_state": state.to_dict(),
        "recommendation": recommendation.to_dict(),
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return path
