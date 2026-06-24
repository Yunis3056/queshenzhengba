from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import sys
import ctypes

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from queshen_agent.watch_analyzer import (
    FrameAnalyzerConfig,
    _file_signature,
    _is_file_stable,
    _write_latest_result,
    _write_latest_text,
    analyze_image_state,
    load_frame_analyzer_config,
)
from queshen_agent.tile import suit_label, tile_label


ROOT = Path(__file__).resolve().parents[1]
WATCH_INBOX = ROOT / "watch" / "inbox"
WATCH_FRAMES = ROOT / "watch" / "frames"
CONFIG_PATH = ROOT / "config" / "quick_capture.json"

# ── 毡台中国风配色 ─────────────────────────────────────────────
T = {
    "bg":          "#143226",   # 毡台墨绿主背景
    "bg_dark":     "#0E2319",   # 稍深底（面板/卡片背景）
    "bg_card":     "#F5F1E6",   # 牙白牌卡背景
    "gold":        "#C9A45C",   # 金色（描边/标题）
    "gold_hi":     "#F2C572",   # 金色高亮（主按钮底色）
    "gold_press":  "#B8903E",   # 金色按下
    "red":         "#C0392B",   # 印章红（推荐牌值 / 停止 / X牌）
    "red_hover":   "#A93226",
    "red_press":   "#922B21",
    "btn_bg":      "#1C4434",   # 次按钮底
    "btn_hover":   "#235140",
    "btn_press":   "#163528",
    "btn_border":  "#356A51",   # 次按钮描边
    "text_main":   "#EFF3EC",   # 主文字（毡绿上）
    "text_dim":    "#9DB3A5",   # 次要文字
    "text_card":   "#2C1A0E",   # 牌卡上深色文字
    "text_card_dim": "#7A6A50", # 牌卡上次要文字
    "entry_bg":    "#0E2319",   # 输入框背景
    "entry_border":"#356A51",
    "entry_focus": "#F2C572",
    "tile_bg":     "#F7F3E8",   # 手牌格牌面
    "tile_empty":  "#1C4434",   # 手牌格空位
    "tile_x_bg":   "#C0392B",   # X牌红底
}
# ──────────────────────────────────────────────────────────────


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


enable_dpi_awareness()


@dataclass
class CaptureConfig:
    x: int = 0
    y: int = 0
    width: int = 1280
    height: int = 720
    output_dir: str = str(WATCH_INBOX)
    frame_dir: str = str(WATCH_FRAMES)
    frame_interval_seconds: float = 1.0
    latest_frame_name: str = "latest.png"
    keep_frame_history: bool = True
    history_dir: str = str(WATCH_FRAMES / "history")
    collect_round_frames: bool = False
    round_dir: str = str(WATCH_FRAMES / "rounds")


def load_config() -> CaptureConfig:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        defaults = asdict(CaptureConfig())
        defaults.update({key: value for key, value in data.items() if key in defaults})
        output_dir_text = str(defaults["output_dir"]).replace("/", "\\")
        if "Documents\\Codex\\2026-06-22\\ni" in output_dir_text:
            defaults["output_dir"] = str(WATCH_INBOX)
        return CaptureConfig(**defaults)
    return CaptureConfig()


def save_config(config: CaptureConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def _round_rect_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    return [
        x1 + radius, y1,  x2 - radius, y1,
        x2, y1,  x2, y1 + radius,
        x2, y2 - radius,  x2, y2,
        x2 - radius, y2,  x1 + radius, y2,
        x1, y2,  x1, y2 - radius,
        x1, y1 + radius,  x1, y1,
    ]


class RoundedButton(tk.Canvas):
    def __init__(self, parent: tk.Widget, text: str, command, *, primary: bool = False) -> None:
        self.parent_bg = parent.cget("bg") if hasattr(parent, "cget") else T["bg"]
        self.command = command
        self.text = text
        self._primary = primary
        self._pressed = False
        self._hovered = False
        self._apply_scheme(primary, base_override=None)
        super().__init__(
            parent,
            width=132,
            height=42,
            bg=self.parent_bg,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _apply_scheme(self, primary: bool, base_override: str | None) -> None:
        if base_override == T["red"]:
            self.fg = "#FFFFFF"
            self.base_color  = T["red"]
            self.hover_color = T["red_hover"]
            self.press_color = T["red_press"]
            self.border_color = T["red"]
        elif primary:
            self.fg = T["text_card"]
            self.base_color  = T["gold_hi"]
            self.hover_color = "#F7D08A"
            self.press_color = T["gold_press"]
            self.border_color = T["gold"]
        else:
            self.fg = T["text_main"]
            self.base_color  = T["btn_bg"]
            self.hover_color = T["btn_hover"]
            self.press_color = T["btn_press"]
            self.border_color = T["btn_border"]

    def config(self, **kwargs) -> None:  # type: ignore[override]
        text = kwargs.pop("text", None)
        bg   = kwargs.pop("bg", None)
        fg   = kwargs.pop("fg", None)
        command = kwargs.pop("command", None)
        if text    is not None: self.text = str(text)
        if command is not None: self.command = command
        if fg      is not None: self.fg = str(fg)
        if bg      is not None:
            self._apply_scheme(self._primary, bg if bg in (T["red"],) else None)
            if bg not in (T["red"],):
                self.base_color = bg
        if kwargs: super().config(**kwargs)
        self._draw()

    configure = config

    def _draw(self) -> None:
        self.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        color = self.press_color if self._pressed else self.hover_color if self._hovered else self.base_color
        self.create_polygon(
            _round_rect_points(1, 1, w - 1, h - 1, 9),
            smooth=True, fill=color, outline=self.border_color,
        )
        self.create_text(
            w // 2, h // 2,
            text=self.text, fill=self.fg,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _on_enter(self, _e):  self._hovered = True;  self._draw()
    def _on_leave(self, _e):  self._hovered = False; self._pressed = False; self._draw()
    def _on_press(self, _e):  self._pressed = True;  self._draw()

    def _on_release(self, event):
        was = self._pressed
        self._pressed = False; self._draw()
        if was and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()


class RoundedEntry(tk.Frame):
    def __init__(self, parent: tk.Widget, *, width: int = 92) -> None:
        self.parent_bg = parent.cget("bg") if hasattr(parent, "cget") else T["bg"]
        super().__init__(parent, width=width, height=34, bg=self.parent_bg)
        self.grid_propagate(False)
        self.canvas = tk.Canvas(self, bg=self.parent_bg, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.entry = tk.Entry(
            self, relief="flat",
            bg=T["entry_bg"], fg=T["text_main"],
            insertbackground=T["gold_hi"],
            bd=0, font=("Microsoft YaHei UI", 10),
        )
        self.entry.place(x=10, y=6, relwidth=1, width=-20, height=22)
        self._border_color = T["entry_border"]
        self.bind("<Configure>", lambda _e: self._draw())
        self.canvas.bind("<Button-1>", lambda _e: self.entry.focus_set())
        self.entry.bind("<FocusIn>",  lambda _e: self._set_border(T["entry_focus"]))
        self.entry.bind("<FocusOut>", lambda _e: self._set_border(T["entry_border"]))
        self._draw()

    def insert(self, index, text: str) -> None: self.entry.insert(index, text)
    def delete(self, first, last=None) -> None:  self.entry.delete(first, last)
    def get(self) -> str: return self.entry.get()

    def _set_border(self, color: str) -> None:
        self._border_color = color; self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        self.canvas.create_polygon(
            _round_rect_points(1, 1, w - 1, h - 1, 9),
            smooth=True, fill=T["entry_bg"], outline=self._border_color,
        )


class QuickCaptureApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("雀神争霸 · AI 教练")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.config = load_config()
        self.analyzer_config = load_frame_analyzer_config()
        self.frame_running = False
        self.frame_after_id: str | None = None
        self.analyzer_after_id: str | None = None
        self.last_analyzed_signature: tuple[int, int] | None = None
        self.round_active = False
        self.current_round_dir: Path | None = None
        self.round_started_at: str | None = None
        self.last_saved_frame_path: Path | None = None
        self.screen_scale_x = 1.0
        self.screen_scale_y = 1.0
        self._build_ui()
        self._update_screen_scale()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_embedded_analyzer()

    def _build_ui(self) -> None:
        self.root.configure(bg=T["bg"])
        outer = tk.Frame(self.root, bg=T["bg"], padx=18, pady=16)
        outer.pack(fill="both", expand=True)

        # ── 标题栏 ──
        title = tk.Label(
            outer, text="雀神争霸 · AI 教练",
            fg=T["gold_hi"], bg=T["bg"],
            font=("Microsoft YaHei UI", 17, "bold"),
        )
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        # ── 截图区域参数 ──
        field_font = ("Microsoft YaHei UI", 10)
        self.entries: dict[str, RoundedEntry] = {}
        for row, key in enumerate(("x", "y", "width", "height"), start=1):
            tk.Label(outer, text=key, fg=T["text_dim"], bg=T["bg"], font=field_font).grid(
                row=row, column=0, sticky="w", pady=3
            )
            entry = RoundedEntry(outer)
            entry.insert(0, str(getattr(self.config, key)))
            entry.grid(row=row, column=1, sticky="w", pady=3)
            self.entries[key] = entry

        tk.Label(outer, text="截帧间隔(秒)", fg=T["text_dim"], bg=T["bg"], font=field_font).grid(
            row=5, column=0, sticky="w", pady=(10, 3)
        )
        self.interval_entry = RoundedEntry(outer)
        self.interval_entry.insert(0, str(self.config.frame_interval_seconds))
        self.interval_entry.grid(row=5, column=1, sticky="w", pady=(10, 3))

        # ── 右侧按钮列 ──
        capture_btn = self._button(outer, "一键截图", self.capture, primary=True)
        capture_btn.grid(row=1, column=2, rowspan=2, padx=(16, 0), pady=3, sticky="nsew")

        save_btn = self._button(outer, "保存区域", self.save_region)
        save_btn.grid(row=3, column=2, rowspan=2, padx=(16, 0), pady=3, sticky="nsew")

        select_btn = self._button(outer, "手动选区", self.select_region)
        select_btn.grid(row=1, column=3, rowspan=4, padx=(10, 0), pady=3, sticky="nsew")

        self.frame_button = self._button(outer, "▶  开始连续截帧", self.toggle_continuous_frames, primary=True)
        self.frame_button.grid(row=5, column=2, columnspan=2, padx=(16, 0), pady=(10, 3), sticky="nsew")

        self.new_round_button = self._button(outer, "新开一局", self.start_new_round)
        self.new_round_button.grid(row=6, column=2, columnspan=2, padx=(16, 0), pady=(6, 3), sticky="nsew")

        # ── 分隔线 ──
        sep = tk.Frame(outer, bg=T["gold"], height=1)
        sep.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(14, 0))

        # ── 实时建议标题 ──
        tk.Label(
            outer, text="实时建议", fg=T["gold"], bg=T["bg"],
            font=("Microsoft YaHei UI", 12, "bold"),
        ).grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 6))

        # ── 推荐牌卡(牙白) ──
        card = tk.Frame(outer, bg=T["bg_card"], highlightthickness=1, highlightbackground=T["gold"])
        card.grid(row=9, column=0, columnspan=4, sticky="nsew", pady=(0, 2))
        card.grid_columnconfigure(1, weight=1)
        self.result_fields: dict[str, tk.Label] = {}

        self._add_result_row(card, 0, "建议打", "recommended", "--",
                             value_font=("Microsoft YaHei UI", 26, "bold"), value_fg=T["red"])
        self._add_result_row(card, 1, "备选",   "alternatives", "--")
        self._add_result_row(card, 2, "定缺",   "missing",      "未识别")
        self._add_result_row(card, 3, "路线",   "route",        "未判断",   wraplength=390)
        self._add_result_row(card, 4, "原因",   "reason",       "等待截帧...", wraplength=390)
        self._add_result_row(card, 5, "风险",   "risk",         "无",       wraplength=390)
        self._add_result_row(card, 6, "置信度", "confidence",   "--")

        # ── 手牌格 ──
        tk.Label(card, text="手牌", fg=T["text_card_dim"], bg=T["bg_card"],
                 font=("Microsoft YaHei UI", 10, "bold")).grid(
            row=7, column=0, sticky="nw", padx=(12, 8), pady=(10, 4)
        )
        hand_grid = tk.Frame(card, bg=T["bg_card"])
        hand_grid.grid(row=7, column=1, sticky="ew", padx=(0, 12), pady=(8, 12))
        self.hand_cells: list[tk.Label] = []
        for i in range(14):
            cell = tk.Label(
                hand_grid, text=str(i + 1), width=4, height=2,
                fg=T["text_dim"], bg=T["tile_empty"],
                font=("Microsoft YaHei UI", 10, "bold"),
            )
            cell.grid(row=i // 7, column=i % 7, padx=2, pady=2, sticky="nsew")
            self.hand_cells.append(cell)

    def _add_result_row(
        self, parent, row, title, key, value, *,
        value_font=("Microsoft YaHei UI", 10),
        value_fg: str = "",
        wraplength: int = 0,
    ) -> None:
        if not value_fg:
            value_fg = T["text_card"]
        tk.Label(
            parent, text=title, fg=T["text_card_dim"], bg=T["bg_card"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).grid(row=row, column=0, sticky="nw",
               padx=(12, 8), pady=(10 if row == 0 else 4, 4))
        lbl = tk.Label(
            parent, text=value, fg=value_fg, bg=T["bg_card"],
            font=value_font, justify="left", anchor="w",
            wraplength=wraplength,
        )
        lbl.grid(row=row, column=1, sticky="ew",
                 padx=(0, 12), pady=(10 if row == 0 else 4, 4))
        self.result_fields[key] = lbl

    def _button(self, parent, text, command, primary=False) -> RoundedButton:
        return RoundedButton(parent, text, command, primary=primary)

    # ── 以下逻辑方法完全不变 ────────────────────────────────────

    def save_region(self) -> None:
        try:
            self.config.x = int(self.entries["x"].get())
            self.config.y = int(self.entries["y"].get())
            self.config.width  = int(self.entries["width"].get())
            self.config.height = int(self.entries["height"].get())
            self.config.frame_interval_seconds = float(self.interval_entry.get())
            if self.config.frame_interval_seconds <= 0:
                raise ValueError
            save_config(self.config)
        except ValueError:
            messagebox.showerror("配置无效", "x/y/width/height 必须是整数，截帧间隔必须是大于 0 的数字。")

    def capture(self) -> None:
        self.save_region()
        try:
            image = self._grab_region()
        except ImportError:
            messagebox.showerror("缺少依赖", "请先安装 Pillow：python -m pip install Pillow")
            return
        except Exception as exc:
            messagebox.showerror("截图失败", str(exc))
            return
        output_dir = resolve_project_path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"queshen_{timestamp}.png"
        image.save(path)

    def toggle_continuous_frames(self) -> None:
        if self.frame_running:
            self.stop_continuous_frames()
        else:
            self.start_continuous_frames()

    def start_continuous_frames(self) -> None:
        self.save_region()
        if self.config.frame_interval_seconds <= 0:
            return
        if not self.round_active or self.current_round_dir is None:
            self._create_round_dir()
        self.frame_running = True
        self.frame_button.config(text="■  停止连续截帧", bg=T["red"])
        self._capture_frame_loop()

    def stop_continuous_frames(self) -> None:
        self.frame_running = False
        if self.frame_after_id is not None:
            self.root.after_cancel(self.frame_after_id)
            self.frame_after_id = None
        self.round_active = False
        self.frame_button.config(text="▶  开始连续截帧", bg=T["gold_hi"])

    def _capture_frame_loop(self) -> None:
        if not self.frame_running:
            return
        try:
            self.capture_latest_frame()
        except ImportError:
            self.stop_continuous_frames()
            messagebox.showerror("缺少依赖", "请先安装 Pillow：python -m pip install Pillow")
            return
        except Exception as exc:
            self.stop_continuous_frames()
            messagebox.showerror("连续截帧失败", str(exc))
            return
        interval_ms = max(100, int(self.config.frame_interval_seconds * 1000))
        self.frame_after_id = self.root.after(interval_ms, self._capture_frame_loop)

    def capture_latest_frame(self) -> Path:
        image = self._grab_region()
        frame_dir = resolve_project_path(self.config.frame_dir)
        frame_dir.mkdir(parents=True, exist_ok=True)
        latest_path = self._latest_frame_path()
        tmp_path = latest_path.with_name(f"{latest_path.stem}.tmp{latest_path.suffix}")
        image.save(tmp_path)
        tmp_path.replace(latest_path)
        history_dir = self._active_history_dir()
        self.last_saved_frame_path = None
        if history_dir is not None:
            history_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.last_saved_frame_path = history_dir / f"frame_{timestamp}.png"
            image.save(self.last_saved_frame_path)
        return latest_path

    def start_new_round(self) -> None:
        self.save_region()
        self.last_analyzed_signature = None
        self._create_round_dir()
        self._set_result_message("新局已开始。")
        try:
            self.capture_latest_frame()
        except Exception as exc:
            self._set_result_message(f"新局已创建，但首帧保存失败：{exc}")
        if not self.frame_running:
            self.start_continuous_frames()

    def _create_round_dir(self) -> Path:
        self.round_active = True
        self.round_started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = resolve_project_path(self.config.round_dir)
        candidate = base_dir / f"round_{self.round_started_at}"
        suffix = 1
        while candidate.exists():
            suffix += 1
            candidate = base_dir / f"round_{self.round_started_at}_{suffix}"
        candidate.mkdir(parents=True, exist_ok=True)
        self.current_round_dir = candidate
        self.last_saved_frame_path = None
        return candidate

    def _active_history_dir(self) -> Path | None:
        if self.round_active and self.current_round_dir is not None:
            return self.current_round_dir
        if self.config.keep_frame_history or self.config.collect_round_frames:
            return resolve_project_path(self.config.history_dir)
        return None

    def start_embedded_analyzer(self) -> None:
        self._schedule_analyzer_poll(250)

    def _schedule_analyzer_poll(self, delay_ms: int | None = None) -> None:
        interval = delay_ms if delay_ms is not None else max(100, int(self.analyzer_config.poll_seconds * 1000))
        self.analyzer_after_id = self.root.after(interval, self._poll_latest_frame)

    def _poll_latest_frame(self) -> None:
        latest_path = self._latest_frame_path()
        signature = _file_signature(latest_path)
        if signature is None or signature == self.last_analyzed_signature:
            self._schedule_analyzer_poll()
            return
        if not _is_file_stable(
            latest_path,
            self.analyzer_config.stable_checks,
            min(0.2, self.analyzer_config.poll_seconds),
        ):
            self._schedule_analyzer_poll()
            return
        signature = _file_signature(latest_path)
        if signature is None or signature == self.last_analyzed_signature:
            self._schedule_analyzer_poll()
            return
        self.last_analyzed_signature = signature
        try:
            state, recommendation = analyze_image_state(latest_path)
            latest_json = self._latest_result_path()
            latest_text = self._latest_text_path()
            _write_latest_result(latest_path, state, recommendation, latest_json)
            _write_latest_text(latest_path, state, recommendation, latest_text)
            self._render_latest_result(state, recommendation)
        except Exception as exc:
            self._set_result_message(f"分析失败：{exc}")
        self._schedule_analyzer_poll()

    def _render_latest_result(self, state, recommendation) -> None:
        recommended  = tile_label(recommendation.recommended_discard) if recommendation.recommended_discard else "--"
        alternatives = "、".join(tile_label(t) for t in recommendation.alternatives) or "无"
        missing      = suit_label(state.missing_suit) if state.missing_suit else "未识别"
        route        = "、".join(recommendation.route) or "未判断"
        risk         = "、".join(recommendation.risk_notes) or "无"
        confidence   = f"识别 {state.recognition_confidence:.0%} / 建议 {recommendation.confidence:.0%}"
        self.result_fields["recommended"].config(text=recommended)
        self.result_fields["alternatives"].config(text=alternatives)
        self.result_fields["missing"].config(text=missing)
        self.result_fields["route"].config(text=route)
        self.result_fields["reason"].config(text=recommendation.reason)
        self.result_fields["risk"].config(text=risk)
        self.result_fields["confidence"].config(text=confidence)
        self._render_hand_cells(state)

    def _set_result_message(self, text: str) -> None:
        self.result_fields["recommended"].config(text="--")
        self.result_fields["alternatives"].config(text="--")
        self.result_fields["missing"].config(text="未识别")
        self.result_fields["route"].config(text="未判断")
        self.result_fields["reason"].config(text=text)
        self.result_fields["risk"].config(text="无")
        self.result_fields["confidence"].config(text="--")
        self._render_hand_cells(None)

    def _render_hand_cells(self, state) -> None:
        display = list(getattr(state, "hand_display", []) or getattr(state, "hand", []) or [])
        for i, cell in enumerate(self.hand_cells):
            if i >= len(display):
                cell.config(text=str(i + 1), fg=T["text_dim"], bg=T["tile_empty"])
                continue
            tile = display[i]
            if tile == "X":
                cell.config(text="X", fg="#FFFFFF", bg=T["tile_x_bg"])
            else:
                cell.config(text=tile_label(tile), fg=T["text_card"], bg=T["tile_bg"])

    def _grab_region(self):
        from PIL import ImageGrab
        bbox = (self.config.x, self.config.y,
                self.config.x + self.config.width, self.config.y + self.config.height)
        return ImageGrab.grab(bbox=bbox)

    def _update_screen_scale(self) -> None:
        try:
            from PIL import ImageGrab
            grabbed = ImageGrab.grab()
            physical_width, physical_height = grabbed.size
            logical_width  = max(1, self.root.winfo_screenwidth())
            logical_height = max(1, self.root.winfo_screenheight())
            self.screen_scale_x = physical_width  / logical_width
            self.screen_scale_y = physical_height / logical_height
        except Exception:
            self.screen_scale_x = 1.0
            self.screen_scale_y = 1.0

    def _logical_to_capture_region(self, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, width, height = region
        return (
            round(x * self.screen_scale_x), round(y * self.screen_scale_y),
            round(width * self.screen_scale_x), round(height * self.screen_scale_y),
        )

    def _latest_frame_path(self) -> Path:
        return resolve_project_path(self.config.frame_dir) / self.config.latest_frame_name

    def _latest_result_path(self) -> Path:
        if self.analyzer_config.latest_result_path is not None:
            return self.analyzer_config.latest_result_path
        return resolve_project_path("watch/results/latest_result.json")

    def _latest_text_path(self) -> Path:
        if self.analyzer_config.latest_text_path is not None:
            return self.analyzer_config.latest_text_path
        return resolve_project_path("watch/results/latest_result.txt")

    def select_region(self) -> None:
        self.root.withdraw()
        selector = RegionSelector(self.root)
        self.root.wait_window(selector.window)
        self.root.deiconify()
        if selector.region is None:
            return
        self._update_screen_scale()
        x, y, width, height = self._logical_to_capture_region(selector.region)
        values = {"x": x, "y": y, "width": width, "height": height}
        for key, value in values.items():
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, str(value))
        self.save_region()

    def run(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        if self.frame_running:
            self.stop_continuous_frames()
        if self.analyzer_after_id is not None:
            self.root.after_cancel(self.analyzer_after_id)
            self.analyzer_after_id = None
        self.root.destroy()


class RegionSelector:
    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.28)
        self.window.configure(bg="black")
        self.window.cursor = "crosshair"
        self.window.bind("<Escape>", self.cancel)
        self.window.bind("<ButtonPress-1>", self.on_press)
        self.window.bind("<B1-Motion>", self.on_drag)
        self.window.bind("<ButtonRelease-1>", self.on_release)
        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            24, 24, anchor="nw",
            text="拖拽选择截图区域，松开确认；按 Esc 取消",
            fill=T["gold_hi"],
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        self.start_x = 0
        self.start_y = 0
        self.rect_id: int | None = None
        self.region: tuple[int, int, int, int] | None = None

    def on_press(self, event: tk.Event) -> None:
        self.start_x = int(event.x_root)
        self.start_y = int(event.y_root)
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline=T["gold_hi"], width=3,
        )

    def on_drag(self, event: tk.Event) -> None:
        if self.rect_id is None:
            return
        sx = self.start_x - self.window.winfo_rootx()
        sy = self.start_y - self.window.winfo_rooty()
        self.canvas.coords(self.rect_id, sx, sy, event.x, event.y)

    def on_release(self, event: tk.Event) -> None:
        ex, ey = int(event.x_root), int(event.y_root)
        x1, x2 = sorted((self.start_x, ex))
        y1, y2 = sorted((self.start_y, ey))
        if x2 - x1 >= 10 and y2 - y1 >= 10:
            self.region = (x1, y1, x2 - x1, y2 - y1)
        self.window.destroy()

    def cancel(self, event: tk.Event | None = None) -> None:
        self.region = None
        self.window.destroy()


if __name__ == "__main__":
    QuickCaptureApp().run()



ROOT = Path(__file__).resolve().parents[1]
WATCH_INBOX = ROOT / "watch" / "inbox"
WATCH_FRAMES = ROOT / "watch" / "frames"
CONFIG_PATH = ROOT / "config" / "quick_capture.json"


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


enable_dpi_awareness()


@dataclass
class CaptureConfig:
    x: int = 0
    y: int = 0
    width: int = 1280
    height: int = 720
    output_dir: str = str(WATCH_INBOX)
    frame_dir: str = str(WATCH_FRAMES)
    frame_interval_seconds: float = 1.0
    latest_frame_name: str = "latest.png"
    keep_frame_history: bool = True
    history_dir: str = str(WATCH_FRAMES / "history")
    collect_round_frames: bool = False
    round_dir: str = str(WATCH_FRAMES / "rounds")


def load_config() -> CaptureConfig:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        defaults = asdict(CaptureConfig())
        defaults.update({key: value for key, value in data.items() if key in defaults})
        output_dir_text = str(defaults["output_dir"]).replace("/", "\\")
        if "Documents\\Codex\\2026-06-22\\ni" in output_dir_text:
            defaults["output_dir"] = str(WATCH_INBOX)
        return CaptureConfig(**defaults)
    return CaptureConfig()


def save_config(config: CaptureConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def _round_rect_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    return [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]


class RoundedButton(tk.Canvas):
    def __init__(self, parent: tk.Widget, text: str, command, *, primary: bool = False) -> None:
        self.parent_bg = parent.cget("bg") if hasattr(parent, "cget") else "#F3F3F3"
        self.command = command
        self.text = text
        self.fg = "#FFFFFF" if primary else "#202020"
        self.base_color = "#0067C0" if primary else "#FFFFFF"
        self.hover_color = "#005A9E" if primary else "#F8F8F8"
        self.press_color = "#004A83" if primary else "#EFEFEF"
        self.border_color = "#0067C0" if primary else "#D0D0D0"
        self._pressed = False
        self._hovered = False
        super().__init__(
            parent,
            width=132,
            height=42,
            bg=self.parent_bg,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def config(self, **kwargs) -> None:  # type: ignore[override]
        text = kwargs.pop("text", None)
        bg = kwargs.pop("bg", None)
        fg = kwargs.pop("fg", None)
        command = kwargs.pop("command", None)
        if text is not None:
            self.text = str(text)
        if command is not None:
            self.command = command
        if fg is not None:
            self.fg = str(fg)
        if bg is not None:
            self._set_base_color(str(bg))
        if kwargs:
            super().config(**kwargs)
        self._draw()

    configure = config

    def _set_base_color(self, color: str) -> None:
        self.base_color = color
        if color.upper() == "#C42B1C":
            self.hover_color = "#A4262C"
            self.press_color = "#8E1F22"
            self.border_color = "#C42B1C"
        elif color.upper() == "#0067C0":
            self.hover_color = "#005A9E"
            self.press_color = "#004A83"
            self.border_color = "#0067C0"
        else:
            self.hover_color = "#F8F8F8"
            self.press_color = "#EFEFEF"
            self.border_color = "#D0D0D0"

    def _draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        color = self.press_color if self._pressed else self.hover_color if self._hovered else self.base_color
        self.create_polygon(
            _round_rect_points(1, 1, width - 1, height - 1, 8),
            smooth=True,
            fill=color,
            outline=self.border_color,
        )
        self.create_text(
            width // 2,
            height // 2,
            text=self.text,
            fill=self.fg,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _on_enter(self, _event: tk.Event) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event: tk.Event) -> None:
        self._pressed = True
        self._draw()

    def _on_release(self, event: tk.Event) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()


class RoundedEntry(tk.Frame):
    def __init__(self, parent: tk.Widget, *, width: int = 92) -> None:
        self.parent_bg = parent.cget("bg") if hasattr(parent, "cget") else "#F3F3F3"
        super().__init__(parent, width=width, height=34, bg=self.parent_bg)
        self.grid_propagate(False)
        self.canvas = tk.Canvas(self, bg=self.parent_bg, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.entry = tk.Entry(
            self,
            relief="flat",
            bg="#FFFFFF",
            fg="#202020",
            insertbackground="#202020",
            bd=0,
            font=("Microsoft YaHei UI", 10),
        )
        self.entry.place(x=10, y=6, relwidth=1, width=-20, height=22)
        self._border_color = "#D0D0D0"
        self.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", lambda _event: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda _event: self._set_border("#0067C0"))
        self.entry.bind("<FocusOut>", lambda _event: self._set_border("#D0D0D0"))
        self._draw()

    def insert(self, index, text: str) -> None:
        self.entry.insert(index, text)

    def delete(self, first, last=None) -> None:
        self.entry.delete(first, last)

    def get(self) -> str:
        return self.entry.get()

    def _set_border(self, color: str) -> None:
        self._border_color = color
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.canvas.create_polygon(
            _round_rect_points(1, 1, width - 1, height - 1, 8),
            smooth=True,
            fill="#FFFFFF",
            outline=self._border_color,
        )


class QuickCaptureApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("雀神一键截图")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.config = load_config()
        self.analyzer_config = load_frame_analyzer_config()
        self.frame_running = False
        self.frame_after_id: str | None = None
        self.analyzer_after_id: str | None = None
        self.last_analyzed_signature: tuple[int, int] | None = None
        self.round_active = False
        self.current_round_dir: Path | None = None
        self.round_started_at: str | None = None
        self.last_saved_frame_path: Path | None = None
        self.screen_scale_x = 1.0
        self.screen_scale_y = 1.0
        self._build_ui()
        self._update_screen_scale()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_embedded_analyzer()

    def _build_ui(self) -> None:
        self.root.configure(bg="#F3F3F3")
        frame = tk.Frame(self.root, padx=16, pady=16, bg="#F3F3F3")
        frame.pack(fill="both", expand=True)

        title = tk.Label(frame, text="雀神争霸教练", fg="#202020", bg="#F3F3F3", font=("Microsoft YaHei UI", 16, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self.entries: dict[str, RoundedEntry] = {}
        for row, key in enumerate(("x", "y", "width", "height"), start=1):
            label = tk.Label(frame, text=key, fg="#424242", bg="#F3F3F3")
            label.grid(row=row, column=0, sticky="w", pady=4)
            entry = RoundedEntry(frame)
            entry.insert(0, str(getattr(self.config, key)))
            entry.grid(row=row, column=1, sticky="w", pady=4)
            self.entries[key] = entry

        interval_label = tk.Label(frame, text="截帧间隔", fg="#424242", bg="#F3F3F3")
        interval_label.grid(row=5, column=0, sticky="w", pady=(10, 4))
        self.interval_entry = RoundedEntry(frame)
        self.interval_entry.insert(0, str(self.config.frame_interval_seconds))
        self.interval_entry.grid(row=5, column=1, sticky="w", pady=(10, 4))

        capture = self._button(frame, "一键截图", self.capture, primary=True)
        capture.grid(row=1, column=2, rowspan=2, padx=(16, 0), pady=4, sticky="nsew")

        save = self._button(frame, "保存区域", self.save_region)
        save.grid(row=3, column=2, rowspan=2, padx=(16, 0), pady=4, sticky="nsew")

        select = self._button(frame, "手动选区", self.select_region)
        select.grid(row=1, column=3, rowspan=4, padx=(10, 0), pady=4, sticky="nsew")

        self.frame_button = self._button(frame, "开始连续截帧", self.toggle_continuous_frames)
        self.frame_button.grid(row=5, column=2, columnspan=2, padx=(16, 0), pady=(10, 4), sticky="nsew")

        self.new_round_button = self._button(frame, "新开一局", self.start_new_round, primary=True)
        self.new_round_button.grid(row=6, column=2, columnspan=2, padx=(16, 0), pady=(8, 4), sticky="nsew")

        result_title = tk.Label(
            frame,
            text="实时建议",
            fg="#202020",
            bg="#F3F3F3",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        result_title.grid(row=7, column=0, columnspan=4, sticky="w", pady=(12, 4))

        result_panel = tk.Frame(frame, bg="#FFFFFF", highlightthickness=1, highlightbackground="#D0D0D0")
        result_panel.grid(row=8, column=0, columnspan=4, sticky="nsew")
        result_panel.grid_columnconfigure(1, weight=1)
        self.result_fields: dict[str, tk.Label] = {}
        self._add_result_row(
            result_panel,
            0,
            "建议打",
            "recommended",
            "--",
            value_font=("Microsoft YaHei UI", 20, "bold"),
            value_fg="#C42B1C",
        )
        self._add_result_row(result_panel, 1, "备选", "alternatives", "--")
        self._add_result_row(result_panel, 2, "定缺", "missing", "未识别")
        self._add_result_row(result_panel, 3, "路线", "route", "未判断", wraplength=390)
        self._add_result_row(result_panel, 4, "原因", "reason", "等待连续帧...", wraplength=390)
        self._add_result_row(result_panel, 5, "风险", "risk", "无", wraplength=390)
        self._add_result_row(result_panel, 6, "置信度", "confidence", "--")

        hand_title = tk.Label(
            result_panel,
            text="手牌",
            fg="#424242",
            bg="#FFFFFF",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        hand_title.grid(row=7, column=0, sticky="nw", padx=(12, 8), pady=(10, 4))
        hand_grid = tk.Frame(result_panel, bg="#FFFFFF")
        hand_grid.grid(row=7, column=1, sticky="ew", padx=(0, 12), pady=(8, 12))
        self.hand_cells: list[tk.Label] = []
        for index in range(14):
            cell = tk.Label(
                hand_grid,
                text=str(index + 1),
                width=4,
                height=2,
                fg="#8A8A8A",
                bg="#F7F7F7",
                relief="solid",
                bd=1,
                font=("Microsoft YaHei UI", 10, "bold"),
            )
            cell.grid(row=index // 7, column=index % 7, padx=2, pady=2, sticky="nsew")
            self.hand_cells.append(cell)

    def _add_result_row(
        self,
        parent: tk.Widget,
        row: int,
        title: str,
        key: str,
        value: str,
        *,
        value_font: tuple[str, int, str] | tuple[str, int] = ("Microsoft YaHei UI", 10),
        value_fg: str = "#202020",
        wraplength: int = 0,
    ) -> None:
        label = tk.Label(
            parent,
            text=title,
            fg="#424242",
            bg="#FFFFFF",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        label.grid(row=row, column=0, sticky="nw", padx=(12, 8), pady=(8 if row == 0 else 4, 4))
        value_label = tk.Label(
            parent,
            text=value,
            fg=value_fg,
            bg="#FFFFFF",
            font=value_font,
            justify="left",
            anchor="w",
            wraplength=wraplength,
        )
        value_label.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=(8 if row == 0 else 4, 4))
        self.result_fields[key] = value_label

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = False) -> RoundedButton:
        return RoundedButton(parent, text, command, primary=primary)

    def save_region(self) -> None:
        try:
            self.config.x = int(self.entries["x"].get())
            self.config.y = int(self.entries["y"].get())
            self.config.width = int(self.entries["width"].get())
            self.config.height = int(self.entries["height"].get())
            self.config.frame_interval_seconds = float(self.interval_entry.get())
            if self.config.frame_interval_seconds <= 0:
                raise ValueError
            save_config(self.config)
        except ValueError:
            messagebox.showerror("配置无效", "x/y/width/height 必须是整数，截帧间隔必须是大于 0 的数字。")

    def capture(self) -> None:
        self.save_region()
        try:
            image = self._grab_region()
        except ImportError:
            messagebox.showerror("缺少依赖", "请先安装 Pillow：python -m pip install Pillow")
            return
        except Exception as exc:
            messagebox.showerror("截图失败", str(exc))
            return

        output_dir = resolve_project_path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"queshen_{timestamp}.png"
        image.save(path)

    def toggle_continuous_frames(self) -> None:
        if self.frame_running:
            self.stop_continuous_frames()
        else:
            self.start_continuous_frames()

    def start_continuous_frames(self) -> None:
        self.save_region()
        if self.config.frame_interval_seconds <= 0:
            return
        if not self.round_active or self.current_round_dir is None:
            self._create_round_dir()
        self.frame_running = True
        self.frame_button.config(text="停止连续截帧", bg="#C42B1C", fg="#FFFFFF")
        self._capture_frame_loop()

    def stop_continuous_frames(self) -> None:
        self.frame_running = False
        if self.frame_after_id is not None:
            self.root.after_cancel(self.frame_after_id)
            self.frame_after_id = None
        self.round_active = False
        self.frame_button.config(text="开始连续截帧", bg="#FFFFFF", fg="#202020")

    def _capture_frame_loop(self) -> None:
        if not self.frame_running:
            return
        try:
            self.capture_latest_frame()
        except ImportError:
            self.stop_continuous_frames()
            messagebox.showerror("缺少依赖", "请先安装 Pillow：python -m pip install Pillow")
            return
        except Exception as exc:
            self.stop_continuous_frames()
            messagebox.showerror("连续截帧失败", str(exc))
            return
        interval_ms = max(100, int(self.config.frame_interval_seconds * 1000))
        self.frame_after_id = self.root.after(interval_ms, self._capture_frame_loop)

    def capture_latest_frame(self) -> Path:
        image = self._grab_region()
        frame_dir = resolve_project_path(self.config.frame_dir)
        frame_dir.mkdir(parents=True, exist_ok=True)
        latest_path = self._latest_frame_path()
        tmp_path = latest_path.with_name(f"{latest_path.stem}.tmp{latest_path.suffix}")
        image.save(tmp_path)
        tmp_path.replace(latest_path)

        history_dir = self._active_history_dir()
        self.last_saved_frame_path = None
        if history_dir is not None:
            history_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.last_saved_frame_path = history_dir / f"frame_{timestamp}.png"
            image.save(self.last_saved_frame_path)
        return latest_path

    def start_new_round(self) -> None:
        self.save_region()
        self.last_analyzed_signature = None
        self._create_round_dir()
        self._set_result_message("新局已开始。")
        try:
            self.capture_latest_frame()
        except Exception as exc:
            self._set_result_message(f"新局已创建，但首帧保存失败：{exc}")
        if not self.frame_running:
            self.start_continuous_frames()

    def _create_round_dir(self) -> Path:
        self.round_active = True
        self.round_started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = resolve_project_path(self.config.round_dir)
        candidate = base_dir / f"round_{self.round_started_at}"
        suffix = 1
        while candidate.exists():
            suffix += 1
            candidate = base_dir / f"round_{self.round_started_at}_{suffix}"
        candidate.mkdir(parents=True, exist_ok=True)
        self.current_round_dir = candidate
        self.last_saved_frame_path = None
        return candidate

    def _active_history_dir(self) -> Path | None:
        if self.round_active and self.current_round_dir is not None:
            return self.current_round_dir
        if self.config.keep_frame_history or self.config.collect_round_frames:
            return resolve_project_path(self.config.history_dir)
        return None

    def start_embedded_analyzer(self) -> None:
        self._schedule_analyzer_poll(250)

    def _schedule_analyzer_poll(self, delay_ms: int | None = None) -> None:
        interval = delay_ms if delay_ms is not None else max(100, int(self.analyzer_config.poll_seconds * 1000))
        self.analyzer_after_id = self.root.after(interval, self._poll_latest_frame)

    def _poll_latest_frame(self) -> None:
        latest_path = self._latest_frame_path()
        signature = _file_signature(latest_path)
        if signature is None or signature == self.last_analyzed_signature:
            self._schedule_analyzer_poll()
            return
        if not _is_file_stable(
            latest_path,
            self.analyzer_config.stable_checks,
            min(0.2, self.analyzer_config.poll_seconds),
        ):
            self._schedule_analyzer_poll()
            return

        signature = _file_signature(latest_path)
        if signature is None or signature == self.last_analyzed_signature:
            self._schedule_analyzer_poll()
            return
        self.last_analyzed_signature = signature
        try:
            state, recommendation = analyze_image_state(latest_path)
            latest_json = self._latest_result_path()
            latest_text = self._latest_text_path()
            _write_latest_result(latest_path, state, recommendation, latest_json)
            _write_latest_text(latest_path, state, recommendation, latest_text)
            self._render_latest_result(state, recommendation)
        except Exception as exc:
            self._set_result_message(f"分析失败：{exc}")
        self._schedule_analyzer_poll()

    def _render_latest_result(self, state, recommendation) -> None:
        recommended = tile_label(recommendation.recommended_discard) if recommendation.recommended_discard else "--"
        alternatives = "、".join(tile_label(tile) for tile in recommendation.alternatives) or "无"
        missing = suit_label(state.missing_suit) if state.missing_suit else "未识别"
        route = "、".join(recommendation.route) or "未判断"
        risk = "、".join(recommendation.risk_notes) or "无"
        confidence = f"识别 {state.recognition_confidence:.0%} / 建议 {recommendation.confidence:.0%}"
        self.result_fields["recommended"].config(text=recommended)
        self.result_fields["alternatives"].config(text=alternatives)
        self.result_fields["missing"].config(text=missing)
        self.result_fields["route"].config(text=route)
        self.result_fields["reason"].config(text=recommendation.reason)
        self.result_fields["risk"].config(text=risk)
        self.result_fields["confidence"].config(text=confidence)
        self._render_hand_cells(state)

    def _set_result_message(self, text: str) -> None:
        self.result_fields["recommended"].config(text="--")
        self.result_fields["alternatives"].config(text="--")
        self.result_fields["missing"].config(text="未识别")
        self.result_fields["route"].config(text="未判断")
        self.result_fields["reason"].config(text=text)
        self.result_fields["risk"].config(text="无")
        self.result_fields["confidence"].config(text="--")
        self._render_hand_cells(None)

    def _render_hand_cells(self, state) -> None:
        display = list(getattr(state, "hand_display", []) or getattr(state, "hand", []) or [])
        for index, cell in enumerate(self.hand_cells):
            if index >= len(display):
                cell.config(text=str(index + 1), fg="#8A8A8A", bg="#F7F7F7")
                continue
            tile = display[index]
            if tile == "X":
                cell.config(text="X", fg="#FFFFFF", bg="#C42B1C")
            else:
                cell.config(text=tile_label(tile), fg="#202020", bg="#FFFFFF")

    def _grab_region(self):
        from PIL import ImageGrab

        bbox = (
            self.config.x,
            self.config.y,
            self.config.x + self.config.width,
            self.config.y + self.config.height,
        )
        return ImageGrab.grab(bbox=bbox)

    def _update_screen_scale(self) -> None:
        try:
            from PIL import ImageGrab

            grabbed = ImageGrab.grab()
            physical_width, physical_height = grabbed.size
            logical_width = max(1, self.root.winfo_screenwidth())
            logical_height = max(1, self.root.winfo_screenheight())
            self.screen_scale_x = physical_width / logical_width
            self.screen_scale_y = physical_height / logical_height
        except Exception:
            self.screen_scale_x = 1.0
            self.screen_scale_y = 1.0

    def _logical_to_capture_region(self, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, width, height = region
        return (
            round(x * self.screen_scale_x),
            round(y * self.screen_scale_y),
            round(width * self.screen_scale_x),
            round(height * self.screen_scale_y),
        )

    def _latest_frame_path(self) -> Path:
        return resolve_project_path(self.config.frame_dir) / self.config.latest_frame_name

    def _latest_result_path(self) -> Path:
        if self.analyzer_config.latest_result_path is not None:
            return self.analyzer_config.latest_result_path
        return resolve_project_path("watch/results/latest_result.json")

    def _latest_text_path(self) -> Path:
        if self.analyzer_config.latest_text_path is not None:
            return self.analyzer_config.latest_text_path
        return resolve_project_path("watch/results/latest_result.txt")

    def select_region(self) -> None:
        self.root.withdraw()
        selector = RegionSelector(self.root)
        self.root.wait_window(selector.window)
        self.root.deiconify()
        if selector.region is None:
            return
        self._update_screen_scale()
        x, y, width, height = self._logical_to_capture_region(selector.region)
        values = {"x": x, "y": y, "width": width, "height": height}
        for key, value in values.items():
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, str(value))
        self.save_region()

    def run(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        if self.frame_running:
            self.stop_continuous_frames()
        if self.analyzer_after_id is not None:
            self.root.after_cancel(self.analyzer_after_id)
            self.analyzer_after_id = None
        self.root.destroy()


class RegionSelector:
    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.28)
        self.window.configure(bg="black")
        self.window.cursor = "crosshair"
        self.window.bind("<Escape>", self.cancel)
        self.window.bind("<ButtonPress-1>", self.on_press)
        self.window.bind("<B1-Motion>", self.on_drag)
        self.window.bind("<ButtonRelease-1>", self.on_release)

        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            24,
            24,
            anchor="nw",
            text="拖拽选择游戏区域，松开鼠标确认；按 Esc 取消",
            fill="#F2C572",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        self.start_x = 0
        self.start_y = 0
        self.rect_id: int | None = None
        self.region: tuple[int, int, int, int] | None = None

    def on_press(self, event: tk.Event) -> None:
        self.start_x = int(event.x_root)
        self.start_y = int(event.y_root)
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#F2C572",
            width=3,
        )

    def on_drag(self, event: tk.Event) -> None:
        if self.rect_id is None:
            return
        start_canvas_x = self.start_x - self.window.winfo_rootx()
        start_canvas_y = self.start_y - self.window.winfo_rooty()
        self.canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, event.x, event.y)

    def on_release(self, event: tk.Event) -> None:
        end_x = int(event.x_root)
        end_y = int(event.y_root)
        x1, x2 = sorted((self.start_x, end_x))
        y1, y2 = sorted((self.start_y, end_y))
        width = x2 - x1
        height = y2 - y1
        if width >= 10 and height >= 10:
            self.region = (x1, y1, width, height)
        self.window.destroy()

    def cancel(self, event: tk.Event | None = None) -> None:
        self.region = None
        self.window.destroy()


if __name__ == "__main__":
    QuickCaptureApp().run()
