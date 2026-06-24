# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows desktop AI coach prototype for the 《燕云十六声》"雀神争霸" (custom mahjong rules) human-vs-AI practice mode. It only offers teaching advice from on-screen pixels — it never reads game memory, never modifies the game, and never auto-clicks. Keep that boundary intact in any change.

**Important**: This is NOT standard Sichuan mahjong. It's a custom ruleset with unique scoring patterns (yaku). See `outputs/yanyun_queshen_rules.json` for the complete rules.

UI text, recommendation reasons, and most config keys are Chinese-facing; code/identifiers are English.

## Running and testing

The package lives under `src/`, so the import root is `src` (`pyproject.toml` sets `pythonpath = ["src"]` for pytest). Either set `PYTHONPATH=src` or use the `run_*.py` wrappers / `.ps1` launchers (the wrappers prepend `src` to `sys.path`; the `.ps1` files prefer `.\.venv\Scripts\python.exe` and force UTF-8).

```powershell
python -m pip install -r requirements.txt          # opencv-python, mss, Pillow, numpy

# Tests (no extra env when using PYTHONPATH)
$env:PYTHONPATH="src"; python -m unittest discover -s tests
$env:PYTHONPATH="src"; python -m unittest tests.test_strategy        # single module
python -m pytest tests/test_strategy.py                              # pytest reads pythonpath from pyproject

# Strategy engine without any screenshots (fastest feedback loop)
$env:PYTHONPATH="src"; python -m queshen_agent.cli --missing-suit p --hand 1m 2m 3m 5m 5m 8m 8m 2s 3s 4s 9p
```

There is no build step and no linter configured.

## Run mode

**`tools/quick_capture.py`** (tkinter, `start_quick_capture.ps1`) is the single entry point — it grabs the screen into `watch/frames/latest.png` every X seconds, runs the analysis pipeline in-process, and shows the result in the same window. Suits phone-mirror-to-PC setups. `tools/quick_capture.py` deliberately imports private helpers (`_write_latest_result`, `_is_file_stable`, etc.) from `watch_analyzer` — that module is the de facto shared analysis library, not just a CLI.

```powershell
.\start_quick_capture.ps1   # recommended (sets UTF-8, prefers .venv)
python tools\quick_capture.py
```

`watch_analyzer` has two watch loops: `watch()` (a directory inbox, history kept) and `watch_latest_frame()` (continuous capture, only `watch/frames/latest.png`, overwrites `watch/results/latest_result.{json,txt}` and skips stale frames unless `keep_result_history` is set). The standalone analyzers (`start_watch_analyzer.ps1` / `start_frame_analyzer.ps1`) are for headless/server use when the capture and analysis run on different machines.

## Core pipeline

`screenshot → recognition → GameState → strategy → RecommendationResult`

- **`tile.py`** — the vocabulary layer. 27 tiles (`m`=万/`p`=筒/`s`=条, ranks 1–9), aggressive normalization of suit/tile aliases (accepts CN chars, pinyin, letters), and `counts_to_27` which is the index basis every shanten/score calculation builds on. Touch this carefully; everything downstream assumes its normalization.
- **`models.py`** — dataclasses (`slots=True`) for the whole data contract: `Region`, `RegionConfig` (all calibrated areas), `TileObservation`, `GameState`, `RecommendationResult`. All have `from_dict`/`to_dict` for JSON round-tripping — extend both sides when adding fields.
- **`recognition.py`** — `TemplateRecognizer` does OpenCV template matching (`TM_CCOEFF_NORMED`) against per-tile PNG samples in `samples/templates/<tile>/`. Pipeline per region: crop → `_segment_tile_boxes` (Otsu threshold → contours → merge adjacent → split wide blobs by expected aspect) → match each box. Low-confidence tiles (< `threshold`, default 0.78) become `"X"` in `hand_display` and populate `uncertain_tiles`; the strategy refuses to advise when any `X` is present. `recognize_missing_suit` uses a separate template set in `samples/missing_suit_templates/` with a runner-up margin gate.
- **`shanten.py`** — standard shanten via memoized recursive meld/taatsu search (`_best_meld_taatsu`, `lru_cache`) plus a seven-pairs variant; `best_shanten` is the min. No honor tiles (27-tile space only).
- **`strategy.py`** — pure functions, no I/O. `recommend_discard` scores each candidate discard (`_score_discard`: shanten delta dominates, then isolation/terminal/visible-count heuristics), with hard overrides: unknown tiles → refuse, hand not 13/14 → refuse (mid-animation), missing-suit tiles get a +10000 forced-discard bonus. `analyze_routes` labels the hand (七对/龙七对/将对/清一色/碰碰胡/听牌…). This is the most-tested module — keep it deterministic and side-effect-free.

### Coordinate convention (easy to get wrong)

`RegionConfig` stores every region in **absolute** game/screen coordinates. `recognition.py` rebases sub-regions against `game_area` via `_relative_region` before cropping the screenshot. When adding a region or a calibration step, store absolute coords and let recognition do the rebasing — don't pre-subtract.

## Rules and config

- **Rules** load from `outputs/yanyun_queshen_rules.json` (`rules.py` → `RuleSet`, with `outputs/*.schema.json` alongside). Key invariants: **no chi (吃)**, **peng/gang allowed**, **dingque (定缺 — a forced missing suit)** must be discarded first, **winning hand ≤ 2 suits**. Custom scoring patterns (yaku) include 天胡/地胡 (x32), 将三龙七对 (x128), 十八罗汉 (x64), and many others — see the rules JSON for the complete list.
- **`config/`** holds runtime JSON, all resolved relative to `PROJECT_ROOT` (see `paths.py`): `regions.json` (live calibration — gitignore-worthy, rewritten by the UI), `regions.example.json` / `regions_1280x720_v2.json` (presets; `apply_1280x720_layout.ps1` → `tools/apply_layout_profile.py` copies a preset into `regions.json`), `quick_capture.json`, `frame_analyzer.json`, `vision_analyzer.json`.
- **`paths.py`** is the single source of truth for every filesystem location (`PROJECT_ROOT = parents[2]` of the package). Add new paths here rather than hardcoding.

## Optional vision-model fallback

`vision_analyzer.py` can replace local template matching with an OpenAI vision call (`/v1/responses`, structured JSON schema output). It is **off by default**; enabled only when `config/vision_analyzer.json` has `enabled: true` AND the env var named by `api_key_env` (default `OPENAI_API_KEY`) is set. `analyze_image_prefer_vision` in `watch_analyzer` chooses vision when available, else falls back to local recognition — both must return the same `GameState`/`RecommendationResult` shape, so keep that contract when editing either path.

## Template collection workflow

Recognition needs sample PNGs before it works. `tools/template_collector.py` (`start_template_collector.ps1`) crops single tiles from a saved table screenshot into `samples/templates/<tile>/`; `--export-candidates` batch-exports crops by current `regions.json` into `samples/template_candidates` for manual labeling. Related helpers: `tools/apply_confirmed_candidates.py`, `tools/candidate_contact_sheet.py`, `tools/template_contact_sheet.py`. If `samples/templates` is empty, `recognize_game_state` returns `recognition_confidence=0.0` and the strategy declines to advise — that's expected, not a bug.
