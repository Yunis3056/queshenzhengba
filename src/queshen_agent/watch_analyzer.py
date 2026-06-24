from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import load_region_config
from .models import GameState, RecommendationResult
from .paths import PROJECT_ROOT
from .recognition import TemplateRecognizer
from .rules import load_rules
from .run_record import save_run_record
from .strategy import recommend_discard
from .tile import suit_label, tile_label
from .vision_analyzer import (
    VisionAnalysis,
    analyze_image_with_vision,
    is_vision_available,
    load_vision_analyzer_config,
)


@dataclass(slots=True)
class WatchConfig:
    inbox_dir: Path
    results_dir: Path
    poll_seconds: float = 0.5
    stable_checks: int = 2


@dataclass(slots=True)
class FrameAnalyzerConfig:
    latest_frame_path: Path
    results_dir: Path
    poll_seconds: float = 0.25
    stable_checks: int = 2
    latest_only: bool = True
    write_latest_result: bool = True
    latest_result_path: Path | None = None
    latest_text_path: Path | None = None
    keep_result_history: bool = False


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
FRAME_CONFIG_PATH = PROJECT_ROOT / "config" / "frame_analyzer.json"


def analyze_image(image_path: Path, results_dir: Path) -> Path:
    state, result = analyze_image_state(image_path)
    record_path = save_run_record(image_path, state, result, results_dir)
    return record_path


def analyze_image_state(image_path: Path) -> tuple[GameState, RecommendationResult]:
    rules = load_rules()
    regions = load_region_config()
    recognizer = TemplateRecognizer()
    if recognizer.is_ready():
        state = recognizer.recognize_game_state(image_path, regions)
    else:
        state = GameState(
            recognition_confidence=0.0,
        )
    result = recommend_discard(state, rules)
    return state, result


def analyze_image_prefer_vision(image_path: Path) -> tuple[GameState, RecommendationResult, str, str | None]:
    vision_config = load_vision_analyzer_config()
    if is_vision_available(vision_config):
        analysis = analyze_image_with_vision(image_path, vision_config)
        if analysis.recommendation is None:
            raise RuntimeError("视觉模型没有返回出牌建议。")
        state = GameState.from_dict(
            {
                "missing_suit": analysis.payload.get("missing_suit"),
                "hand": analysis.payload.get("hand", []),
                "drawn_tile": analysis.payload.get("drawn_tile"),
                "recognition_confidence": float(analysis.payload.get("confidence", 0.0)),
            }
        )
        return state, analysis.recommendation, "vision", analysis.text
    state, result = analyze_image_state(image_path)
    return state, result, "local", None


def load_frame_analyzer_config(path: Path = FRAME_CONFIG_PATH) -> FrameAnalyzerConfig:
    defaults = {
        "latest_frame_path": PROJECT_ROOT / "watch" / "frames" / "latest.png",
        "results_dir": PROJECT_ROOT / "watch" / "results",
        "poll_seconds": 0.25,
        "stable_checks": 2,
        "latest_only": True,
        "write_latest_result": True,
        "latest_result_path": PROJECT_ROOT / "watch" / "results" / "latest_result.json",
        "latest_text_path": PROJECT_ROOT / "watch" / "results" / "latest_result.txt",
        "keep_result_history": False,
    }
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        defaults.update({key: value for key, value in data.items() if key in defaults})
    return FrameAnalyzerConfig(
        latest_frame_path=_resolve_project_path(defaults["latest_frame_path"]),
        results_dir=_resolve_project_path(defaults["results_dir"]),
        poll_seconds=float(defaults["poll_seconds"]),
        stable_checks=int(defaults["stable_checks"]),
        latest_only=bool(defaults["latest_only"]),
        write_latest_result=bool(defaults["write_latest_result"]),
        latest_result_path=(
            _resolve_project_path(defaults["latest_result_path"])
            if defaults["latest_result_path"]
            else None
        ),
        latest_text_path=(
            _resolve_project_path(defaults["latest_text_path"])
            if defaults["latest_text_path"]
            else None
        ),
        keep_result_history=bool(defaults["keep_result_history"]),
    )


def watch(config: WatchConfig) -> None:
    config.inbox_dir.mkdir(parents=True, exist_ok=True)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    seen: set[Path] = set()
    print(f"Watching: {config.inbox_dir}")
    print(f"Results:  {config.results_dir}")
    while True:
        for image_path in sorted(config.inbox_dir.iterdir()):
            if image_path in seen:
                continue
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if not _is_file_stable(image_path, config.stable_checks, config.poll_seconds):
                continue
            seen.add(image_path)
            try:
                result_path = analyze_image(image_path, config.results_dir)
                print(json.dumps({"image": str(image_path), "result": str(result_path)}, ensure_ascii=False))
            except Exception as exc:
                error_path = config.results_dir / f"{image_path.stem}.error.json"
                error_path.write_text(
                    json.dumps(
                        {"image": str(image_path), "error": str(exc)},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(json.dumps({"image": str(image_path), "error": str(exc)}, ensure_ascii=False))
        time.sleep(config.poll_seconds)


def watch_latest_frame(config: FrameAnalyzerConfig) -> None:
    config.results_dir.mkdir(parents=True, exist_ok=True)
    if config.latest_result_path:
        config.latest_result_path.parent.mkdir(parents=True, exist_ok=True)
    if config.latest_text_path:
        config.latest_text_path.parent.mkdir(parents=True, exist_ok=True)
    last_signature: tuple[int, int] | None = None
    print(f"Watching latest frame: {config.latest_frame_path}")
    print(f"Results:               {config.results_dir}")
    while True:
        signature = _file_signature(config.latest_frame_path)
        if signature is None or signature == last_signature:
            time.sleep(config.poll_seconds)
            continue
        if not _is_file_stable(config.latest_frame_path, config.stable_checks, config.poll_seconds):
            time.sleep(config.poll_seconds)
            continue

        signature = _file_signature(config.latest_frame_path)
        if signature is None or signature == last_signature:
            time.sleep(config.poll_seconds)
            continue
        last_signature = signature

        try:
            state, result, source, vision_text = analyze_image_prefer_vision(config.latest_frame_path)
            result_path = None
            if config.keep_result_history:
                result_path = save_run_record(config.latest_frame_path, state, result, config.results_dir)
            if config.write_latest_result and config.latest_result_path is not None:
                _write_latest_result(config.latest_frame_path, state, result, config.latest_result_path, source=source)
            if config.latest_text_path is not None:
                _write_latest_text(
                    config.latest_frame_path,
                    state,
                    result,
                    config.latest_text_path,
                    source=source,
                    override_text=vision_text,
                )
            print(
                json.dumps(
                    {
                        "image": str(config.latest_frame_path),
                        "result": str(result_path) if result_path else None,
                        "latest_result": (
                            str(config.latest_result_path)
                            if config.write_latest_result and config.latest_result_path is not None
                            else None
                        ),
                        "latest_text": str(config.latest_text_path) if config.latest_text_path else None,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            error_path = config.results_dir / f"{config.latest_frame_path.stem}.error.json"
            error_path.write_text(
                json.dumps(
                    {"image": str(config.latest_frame_path), "error": str(exc)},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(json.dumps({"image": str(config.latest_frame_path), "error": str(exc)}, ensure_ascii=False))
        time.sleep(config.poll_seconds)


def _is_file_stable(path: Path, checks: int, interval: float) -> bool:
    last = -1
    for _ in range(checks):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size <= 0:
            return False
        if last == size:
            return True
        last = size
        time.sleep(interval)
    return True


def _file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    if stat.st_size <= 0:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _write_latest_result(
    image_path: Path,
    state: GameState,
    recommendation: RecommendationResult,
    target: Path,
    *,
    source: str = "local",
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.stem}.tmp{target.suffix}")
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "screenshot_path": str(image_path),
        "game_state": state.to_dict(),
        "recommendation": recommendation.to_dict(),
    }
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(target)


def _write_latest_text(
    image_path: Path,
    state: GameState,
    recommendation: RecommendationResult,
    target: Path,
    *,
    source: str = "local",
    override_text: str | None = None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.stem}.tmp{target.suffix}")
    recommended = (
        tile_label(recommendation.recommended_discard)
        if recommendation.recommended_discard
        else "--"
    )
    alternatives = "、".join(tile_label(tile) for tile in recommendation.alternatives) or "无"
    hand = _format_hand_display(state) or "未识别"
    drawn = tile_label(state.drawn_tile) if state.drawn_tile else "无"
    missing = suit_label(state.missing_suit) if state.missing_suit else "未识别"
    route = "、".join(recommendation.route) or "未判断"
    uncertain = _format_uncertain_tiles(state)
    if override_text:
        lines = [override_text.rstrip()]
    else:
        lines = [
            f"建议打：{recommended}",
            f"备选：{alternatives}",
            f"原因：{recommendation.reason}",
            f"定缺：{missing}",
            f"路线：{route}",
            f"手牌：{hand}",
            f"摸牌：{drawn}",
            f"未确认牌：{uncertain}",
            f"识别置信度：{state.recognition_confidence:.0%}",
            f"建议置信度：{recommendation.confidence:.0%}",
        ]
    if recommendation.risk_notes:
        lines.append("风险：" + "、".join(recommendation.risk_notes))
    lines.extend(
        [
            "",
            f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"来源：{'视觉模型' if source == 'vision' else '本地识别'}",
            f"截图：{image_path}",
        ]
    )
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_path.replace(target)


def _format_hand_display(state: GameState) -> str:
    display = state.hand_display or state.hand
    return " ".join("X" if tile == "X" else tile_label(tile) for tile in display)


def _format_uncertain_tiles(state: GameState) -> str:
    if not state.uncertain_tiles:
        return "无"
    parts = []
    for index, obs in enumerate(state.uncertain_tiles, start=1):
        label = "X" if obs.tile == "unknown" else tile_label(obs.tile)
        parts.append(f"{index}:{label}({obs.confidence:.0%})")
    return "、".join(parts)


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch screenshots and analyze new files.")
    parser.add_argument("--latest-frame-mode", action="store_true", help="Watch one latest frame file instead of a directory.")
    parser.add_argument("--frame-config", type=Path, default=FRAME_CONFIG_PATH)
    parser.add_argument("--latest-frame", type=Path)
    parser.add_argument("--inbox", type=Path, default=PROJECT_ROOT / "watch" / "inbox")
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "watch" / "results")
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if args.latest_frame_mode or args.latest_frame is not None:
        config = load_frame_analyzer_config(args.frame_config)
        if args.latest_frame is not None:
            config.latest_frame_path = args.latest_frame
        if args.results != PROJECT_ROOT / "watch" / "results":
            config.results_dir = args.results
            if config.latest_result_path == PROJECT_ROOT / "watch" / "results" / "latest_result.json":
                config.latest_result_path = args.results / "latest_result.json"
            if config.latest_text_path == PROJECT_ROOT / "watch" / "results" / "latest_result.txt":
                config.latest_text_path = args.results / "latest_result.txt"
        if args.poll_seconds != 0.5:
            config.poll_seconds = args.poll_seconds
        watch_latest_frame(config)
    else:
        watch(WatchConfig(args.inbox, args.results, args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
