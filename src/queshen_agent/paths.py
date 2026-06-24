from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SAMPLES_DIR = PROJECT_ROOT / "samples"
SCREENSHOTS_DIR = SAMPLES_DIR / "screenshots"
TEMPLATES_DIR = SAMPLES_DIR / "templates"
MISSING_SUIT_TEMPLATES_DIR = SAMPLES_DIR / "missing_suit_templates"
RUNS_DIR = SAMPLES_DIR / "runs"

RULES_PATH = OUTPUTS_DIR / "yanyun_queshen_rules.json"
REGIONS_PATH = CONFIG_DIR / "regions.json"
