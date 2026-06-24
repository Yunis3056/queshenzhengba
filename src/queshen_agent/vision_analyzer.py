from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import RecommendationResult
from .paths import PROJECT_ROOT, RULES_PATH
from .tile import suit_label, tile_label


VISION_CONFIG_PATH = PROJECT_ROOT / "config" / "vision_analyzer.json"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(slots=True)
class VisionAnalyzerConfig:
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: float = 30.0
    max_output_tokens: int = 700
    rules_path: Path = RULES_PATH


@dataclass(slots=True)
class VisionAnalysis:
    text: str
    payload: dict[str, Any]
    recommendation: RecommendationResult | None


def load_vision_analyzer_config(path: Path = VISION_CONFIG_PATH) -> VisionAnalyzerConfig:
    defaults: dict[str, Any] = {
        "enabled": False,
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "api_key_env": "OPENAI_API_KEY",
        "timeout_seconds": 30.0,
        "max_output_tokens": 700,
        "rules_path": RULES_PATH,
    }
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        defaults.update({key: value for key, value in data.items() if key in defaults})
    return VisionAnalyzerConfig(
        enabled=bool(defaults["enabled"]),
        provider=str(defaults["provider"]),
        model=str(defaults["model"]),
        api_key_env=str(defaults["api_key_env"]),
        timeout_seconds=float(defaults["timeout_seconds"]),
        max_output_tokens=int(defaults["max_output_tokens"]),
        rules_path=_resolve_project_path(defaults["rules_path"]),
    )


def is_vision_available(config: VisionAnalyzerConfig) -> bool:
    return bool(config.enabled and config.provider == "openai" and os.environ.get(config.api_key_env))


def analyze_image_with_vision(
    image_path: Path,
    config: VisionAnalyzerConfig | None = None,
) -> VisionAnalysis:
    config = config or load_vision_analyzer_config()
    if not config.enabled:
        raise RuntimeError("视觉分析未启用。")
    if config.provider != "openai":
        raise RuntimeError(f"暂不支持视觉分析提供方：{config.provider}")
    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        raise RuntimeError(f"未设置环境变量 {config.api_key_env}，无法调用视觉模型。")

    image_data_url = _image_to_data_url(image_path)
    payload = {
        "model": config.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _build_prompt(config.rules_path)},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "queshen_recommendation",
                "schema": _response_schema(),
                "strict": True,
            }
        },
        "max_output_tokens": config.max_output_tokens,
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"视觉模型请求失败：HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"视觉模型请求失败：{exc.reason}") from exc

    text = _extract_response_text(response_data)
    parsed = json.loads(text)
    recommendation = _recommendation_from_payload(parsed)
    return VisionAnalysis(text=_format_human_text(parsed), payload=parsed, recommendation=recommendation)


def _build_prompt(rules_path: Path) -> str:
    rules_summary = _load_rules_summary(rules_path)
    return (
        "你是《燕云十六声》雀神争霸人机练习教练。只根据截图可见信息给教学建议，"
        "不要假装能读内存或知道不可见牌。请先识别我方手牌、摸牌、定缺和可见副露/弃牌，"
        "再按规则建议当前最该打出的牌。若截图看不清，必须明确说无法判断。\n\n"
        "牌码：m=万，p=筒，s=条，例如 7m=七万，3p=三筒。\n"
        "重要规则：不能吃；可以碰杠；有定缺，缺门牌优先打；胡牌时不能超过两门花色；"
        "优先考虑七对/龙七对、碰碰胡、清一色、将对/将七对等路线。\n\n"
        f"规则摘要：{rules_summary}\n\n"
        "输出必须是 JSON，字段含义按 schema。recommended_discard 用牌码；看不清则为 null。"
    )


def _load_rules_summary(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return "使用雀神争霸默认规则。"
    fan = ", ".join(
        f"{item.get('label_zh')}x{item.get('multiplier')}"
        for item in data.get("fan_patterns", [])[:12]
    )
    guidance = "；".join(data.get("agent_guidance", {}).get("decision_priorities", [])[:4])
    return f"番型示例：{fan}。决策优先级：{guidance}"


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recommended_discard": {"type": ["string", "null"]},
            "alternatives": {"type": "array", "items": {"type": "string"}},
            "hand": {"type": "array", "items": {"type": "string"}},
            "drawn_tile": {"type": ["string", "null"]},
            "missing_suit": {"type": ["string", "null"]},
            "route": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
            "risk_notes": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        },
        "required": [
            "recommended_discard",
            "alternatives",
            "hand",
            "drawn_tile",
            "missing_suit",
            "route",
            "reason",
            "risk_notes",
            "confidence",
        ],
    }


def _image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _extract_response_text(response_data: dict[str, Any]) -> str:
    if isinstance(response_data.get("output_text"), str):
        return response_data["output_text"]
    texts: list[str] = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if not texts:
        raise RuntimeError("视觉模型没有返回可解析文本。")
    return "\n".join(texts)


def _recommendation_from_payload(payload: dict[str, Any]) -> RecommendationResult:
    return RecommendationResult(
        recommended_discard=payload.get("recommended_discard"),
        alternatives=list(payload.get("alternatives", [])),
        route=list(payload.get("route", [])),
        reason=str(payload.get("reason", "")),
        risk_notes=list(payload.get("risk_notes", [])),
        confidence=float(payload.get("confidence", 0.0)),
    )


def _safe_label(tile: str) -> str:
    # P4：视觉路径也走 tile_label 归一（7m→七万），与本地路径一致；非法牌码回退原串。
    try:
        return tile_label(tile)
    except (ValueError, TypeError):
        return str(tile)


def _format_human_text(payload: dict[str, Any]) -> str:
    recommended_raw = payload.get("recommended_discard")
    recommended = _safe_label(recommended_raw) if recommended_raw else "--"
    alternatives = "、".join(_safe_label(tile) for tile in payload.get("alternatives", [])) or "无"
    hand = " ".join(_safe_label(tile) for tile in payload.get("hand", [])) or "未识别"
    drawn_raw = payload.get("drawn_tile")
    drawn = _safe_label(drawn_raw) if drawn_raw else "无"
    route = "、".join(payload.get("route", [])) or "未判断"
    risks = "、".join(payload.get("risk_notes", [])) or "无"
    return (
        f"建议打：{recommended}\n"
        f"备选：{alternatives}\n"
        f"手牌：{hand}\n"
        f"摸牌：{drawn}\n"
        f"定缺：{suit_label(payload.get('missing_suit'))}\n"
        f"路线：{route}\n"
        f"原因：{payload.get('reason', '')}\n"
        f"风险：{risks}\n"
        f"置信度：{float(payload.get('confidence', 0.0)):.0%}\n"
    )


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
