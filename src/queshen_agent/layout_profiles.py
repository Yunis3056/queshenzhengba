from __future__ import annotations

import json

from .models import RegionConfig
from .paths import PROJECT_ROOT


PROFILE_1280X720_V2 = PROJECT_ROOT / "config" / "regions_1280x720_v2.json"


def load_profile_1280x720_v2() -> RegionConfig:
    with PROFILE_1280X720_V2.open("r", encoding="utf-8") as file:
        return RegionConfig.from_dict(json.load(file))
