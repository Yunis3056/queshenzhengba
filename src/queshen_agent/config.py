from __future__ import annotations

import json
from pathlib import Path

from .models import RegionConfig
from .paths import CONFIG_DIR, REGIONS_PATH


def load_region_config(path: Path = REGIONS_PATH) -> RegionConfig:
    if not path.exists():
        return RegionConfig()
    with path.open("r", encoding="utf-8") as file:
        return RegionConfig.from_dict(json.load(file))


def save_region_config(config: RegionConfig, path: Path = REGIONS_PATH) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config.to_dict(), file, ensure_ascii=False, indent=2)
