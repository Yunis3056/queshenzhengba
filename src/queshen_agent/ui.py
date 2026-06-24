from __future__ import annotations

import json
from pathlib import Path

from .config import load_region_config, save_region_config
from .models import GameState, Region, RegionConfig
from .recognition import TemplateRecognizer, ensure_template_dirs
from .rules import load_rules
from .run_record import save_run_record
from .screenshot import capture_region
from .strategy import recommend_discard
from .tile import tile_label


def _require_qt():
    try:
        from PySide6.QtCore import QPoint, QRect, Qt, Signal
        from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QDialog,
            QFrame,
            QGraphicsDropShadowEffect,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QPlainTextEdit,
            QSizePolicy,
            QTabWidget,
            QTextEdit,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError(
            "桌面界面需要安装依赖：python -m pip install -r requirements.txt"
        ) from exc
    return {
        "QPoint": QPoint,
        "QRect": QRect,
        "Qt": Qt,
        "Signal": Signal,
        "QColor": QColor,
        "QGuiApplication": QGuiApplication,
        "QPainter": QPainter,
        "QPen": QPen,
        "QApplication": QApplication,
        "QComboBox": QComboBox,
        "QDialog": QDialog,
        "QFrame": QFrame,
        "QGraphicsDropShadowEffect": QGraphicsDropShadowEffect,
        "QGridLayout": QGridLayout,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QPlainTextEdit": QPlainTextEdit,
        "QSizePolicy": QSizePolicy,
        "QTabWidget": QTabWidget,
        "QTextEdit": QTextEdit,
        "QToolButton": QToolButton,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def run_app() -> int:
    qt = _require_qt()
    QApplication = qt["QApplication"]
    app = QApplication([])
    app.setApplicationName("雀神争霸 AI 教练")
    window = CoachWindow(qt)
    window.show()
    return app.exec()


def _make_collapsible(qt: dict[str, object], title: str, content, expanded: bool = False):
    """轻量折叠分组：QToolButton 头部(▸/▾) 控制 content 显隐。"""
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QToolButton = qt["QToolButton"]
    QSizePolicy = qt["QSizePolicy"]

    container = QWidget()
    container.setObjectName("Section")
    box = QVBoxLayout(container)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(0)

    header = QToolButton()
    header.setObjectName("SectionHeader")
    header.setCheckable(True)
    header.setChecked(expanded)
    header.setText(("▾  " if expanded else "▸  ") + title)
    header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    header.setCursor(qt["Qt"].CursorShape.PointingHandCursor)

    content.setVisible(expanded)

    def _on_toggled(checked: bool) -> None:
        content.setVisible(checked)
        header.setText(("▾  " if checked else "▸  ") + title)

    header.toggled.connect(_on_toggled)

    box.addWidget(header)
    box.addWidget(content)
    return container


class RegionPicker:
    def __new__(cls, qt: dict[str, object], title: str):
        QDialog = qt["QDialog"]
        Signal = qt["Signal"]
        Qt = qt["Qt"]
        QRect = qt["QRect"]
        QPoint = qt["QPoint"]
        QPainter = qt["QPainter"]
        QPen = qt["QPen"]
        QColor = qt["QColor"]
        QGuiApplication = qt["QGuiApplication"]

        class _RegionPicker(QDialog):
            region_selected = Signal(object)

            def __init__(self) -> None:
                super().__init__()
                self.setWindowTitle(title)
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint
                    | Qt.WindowType.Tool
                )
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                geometry = QGuiApplication.primaryScreen().geometry()
                self.setGeometry(geometry)
                self.start = QPoint()
                self.end = QPoint()
                self.dragging = False

            def mousePressEvent(self, event) -> None:
                self.start = event.globalPosition().toPoint()
                self.end = self.start
                self.dragging = True
                self.update()

            def mouseMoveEvent(self, event) -> None:
                if self.dragging:
                    self.end = event.globalPosition().toPoint()
                    self.update()

            def mouseReleaseEvent(self, event) -> None:
                self.dragging = False
                self.end = event.globalPosition().toPoint()
                rect = QRect(self.start, self.end).normalized()
                self.region_selected.emit(
                    Region(rect.x(), rect.y(), rect.width(), rect.height())
                )
                self.accept()

            def keyPressEvent(self, event) -> None:
                if event.key() == Qt.Key.Key_Escape:
                    self.reject()

            def paintEvent(self, event) -> None:
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
                if not self.start.isNull() and not self.end.isNull():
                    rect = QRect(self.start, self.end).normalized()
                    painter.setPen(QPen(QColor("#F2C572"), 3))
                    painter.drawRect(rect)
                    painter.fillRect(rect, QColor(242, 197, 114, 35))

        return _RegionPicker()


class CoachWindow:
    def __new__(cls, qt: dict[str, object]):
        Qt = qt["Qt"]
        QMainWindow = qt["QMainWindow"]
        QWidget = qt["QWidget"]
        QVBoxLayout = qt["QVBoxLayout"]
        QHBoxLayout = qt["QHBoxLayout"]
        QGridLayout = qt["QGridLayout"]
        QLabel = qt["QLabel"]
        QPushButton = qt["QPushButton"]
        QPlainTextEdit = qt["QPlainTextEdit"]
        QTextEdit = qt["QTextEdit"]
        QLineEdit = qt["QLineEdit"]
        QComboBox = qt["QComboBox"]
        QTabWidget = qt["QTabWidget"]
        QMessageBox = qt["QMessageBox"]
        QFrame = qt["QFrame"]

        class _CoachWindow(QMainWindow):
            def __init__(self) -> None:
                super().__init__()
                self.setWindowTitle("雀神争霸 AI 教练")
                self.setWindowFlags(
                    self.windowFlags()
                    | Qt.WindowType.WindowStaysOnTopHint
                )
                self.resize(460, 680)
                self.region_config = load_region_config()
                self.rules = load_rules()
                self.recognizer = TemplateRecognizer()
                self.latest_screenshot: Path | None = None
                self.latest_state = GameState()
                self._build_ui()
                self._apply_style()
                self._update_status("准备就绪")

            def _build_ui(self) -> None:
                AlignFlag = Qt.AlignmentFlag
                root = QWidget()
                root.setObjectName("Root")
                layout = QVBoxLayout(root)
                layout.setContentsMargins(18, 16, 18, 16)
                layout.setSpacing(14)

                # 顶部栏：标题 + 状态徽标
                header = QHBoxLayout()
                title = QLabel("雀神争霸 · AI 教练")
                title.setObjectName("Title")
                self.status_label = QLabel("")
                self.status_label.setObjectName("Status")
                self.status_label.setAlignment(AlignFlag.AlignRight | AlignFlag.AlignVCenter)
                header.addWidget(title)
                header.addStretch()
                header.addWidget(self.status_label)
                layout.addLayout(header)

                # 推荐牌卡：牙白麻将牌主视觉
                tile_card = QFrame()
                tile_card.setObjectName("TileCard")
                tile_box = QVBoxLayout(tile_card)
                tile_box.setContentsMargins(20, 14, 20, 16)
                tile_box.setSpacing(4)
                caption = QLabel("建议打出")
                caption.setObjectName("TileCaption")
                caption.setAlignment(AlignFlag.AlignHCenter)
                self.recommend_label = QLabel("--")
                self.recommend_label.setObjectName("TileFace")
                self.recommend_label.setAlignment(AlignFlag.AlignCenter)
                self.alt_label = QLabel("备选：无")
                self.alt_label.setObjectName("TileAlt")
                self.alt_label.setAlignment(AlignFlag.AlignCenter)
                tile_box.addWidget(caption)
                tile_box.addWidget(self.recommend_label)
                tile_box.addWidget(self.alt_label)
                shadow = qt["QGraphicsDropShadowEffect"]()
                shadow.setBlurRadius(26)
                shadow.setColor(qt["QColor"](0, 0, 0, 170))
                shadow.setOffset(0, 5)
                tile_card.setGraphicsEffect(shadow)
                layout.addWidget(tile_card)

                # 置信度进度条
                conf_row = QHBoxLayout()
                conf_caption = QLabel("置信度")
                conf_caption.setObjectName("FieldLabel")
                self.confidence_bar = qt["QProgressBar"]()
                self.confidence_bar.setRange(0, 100)
                self.confidence_bar.setValue(0)
                self.confidence_bar.setFormat("%p%")
                conf_row.addWidget(conf_caption)
                conf_row.addWidget(self.confidence_bar, 1)
                layout.addLayout(conf_row)

                # 理由卡
                self.reason_label = QLabel("先选择游戏区域并校准牌区。")
                self.reason_label.setWordWrap(True)
                self.reason_label.setObjectName("Reason")
                layout.addWidget(self.reason_label)

                # 主操作：截图识别（强调）
                self.capture_button = QPushButton("一键截图识别")
                self.capture_button.setObjectName("Primary")
                self.capture_button.clicked.connect(self.capture_and_analyze)
                layout.addWidget(self.capture_button)

                sub_row = QHBoxLayout()
                save_button = QPushButton("保存样本")
                save_button.clicked.connect(self.save_latest_record)
                collapse_button = QPushButton("折叠 / 展开窗口")
                collapse_button.clicked.connect(self.toggle_compact)
                sub_row.addWidget(save_button)
                sub_row.addWidget(collapse_button)
                layout.addLayout(sub_row)

                # 折叠分组：区域校准（默认展开）
                calib_content = QWidget()
                calib_grid = QGridLayout(calib_content)
                calib_grid.setContentsMargins(8, 8, 8, 10)
                calib_grid.setSpacing(8)
                calib_buttons = [
                    ("选择游戏区域", self.pick_game_area),
                    ("校准手牌区", lambda: self.pick_region("hand")),
                    ("校准待打牌", lambda: self.pick_region("drawn_tile")),
                    ("校准自己碰杠", lambda: self.pick_region("self_melds")),
                    ("校准倒计时", lambda: self.pick_region("turn_timer")),
                    ("初始化模板目录", self.init_templates),
                ]
                for index, (text, handler) in enumerate(calib_buttons):
                    button = QPushButton(text)
                    button.clicked.connect(handler)
                    calib_grid.addWidget(button, index // 2, index % 2)
                layout.addWidget(_make_collapsible(qt, "区域校准", calib_content, expanded=True))

                # 折叠分组：对手区域校准
                opp_content = QWidget()
                opp_grid = QGridLayout(opp_content)
                opp_grid.setContentsMargins(8, 8, 8, 10)
                opp_grid.setSpacing(8)
                seat_names = {"left": "左家", "top": "对家", "right": "右家"}
                for col, seat in enumerate(("left", "top", "right")):
                    seat_label = QLabel(seat_names[seat])
                    seat_label.setObjectName("FieldLabel")
                    seat_label.setAlignment(AlignFlag.AlignCenter)
                    discard_button = QPushButton("弃牌")
                    discard_button.clicked.connect(lambda checked=False, s=seat: self.pick_region(f"opponent_discards.{s}"))
                    meld_button = QPushButton("碰杠")
                    meld_button.clicked.connect(lambda checked=False, s=seat: self.pick_region(f"opponent_melds.{s}"))
                    opp_grid.addWidget(seat_label, 0, col)
                    opp_grid.addWidget(discard_button, 1, col)
                    opp_grid.addWidget(meld_button, 2, col)
                layout.addWidget(_make_collapsible(qt, "对手区域校准", opp_content))

                # 折叠分组：手动兜底输入
                manual_content = QWidget()
                manual_grid = QGridLayout(manual_content)
                manual_grid.setContentsMargins(8, 8, 8, 10)
                manual_grid.setSpacing(8)
                self.manual_missing = QComboBox()
                self.manual_missing.addItems(["未知", "万", "筒", "条"])
                self.manual_hand = QLineEdit()
                self.manual_hand.setPlaceholderText("例如：1m 2m 3m 5p 5p 8s")
                manual_button = QPushButton("用手动牌面分析")
                manual_button.clicked.connect(self.analyze_manual)
                dingque_label = QLabel("定缺")
                dingque_label.setObjectName("FieldLabel")
                manual_grid.addWidget(dingque_label, 0, 0)
                manual_grid.addWidget(self.manual_missing, 0, 1)
                manual_grid.addWidget(self.manual_hand, 1, 0, 1, 2)
                manual_grid.addWidget(manual_button, 2, 0, 1, 2)
                layout.addWidget(_make_collapsible(qt, "手动兜底输入", manual_content))

                # 底部 Tab：路线 / 识别详情
                tabs = QTabWidget()
                self.route_text = QTextEdit()
                self.route_text.setReadOnly(True)
                self.detail_text = QPlainTextEdit()
                self.detail_text.setReadOnly(True)
                tabs.addTab(self.route_text, "路线")
                tabs.addTab(self.detail_text, "识别详情")
                layout.addWidget(tabs, 1)

                self.setCentralWidget(root)
                self._compact = False

            def _apply_style(self) -> None:
                self.setStyleSheet(
                    """
                    QMainWindow { background: #0C1F18; }
                    QWidget#Root {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #15392B, stop:0.55 #102A20, stop:1 #0B1C15);
                    }
                    QWidget {
                        color: #EEF2EA;
                        font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC";
                        font-size: 14px;
                    }
                    QLabel#Title {
                        font-size: 21px;
                        font-weight: 800;
                        color: #F2C572;
                        letter-spacing: 1px;
                    }
                    QLabel#Status { color: #9DB3A5; font-size: 12px; }
                    QLabel#FieldLabel { color: #B8C8BC; font-size: 13px; }

                    QFrame#TileCard {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #FAF7EE, stop:1 #ECE6D4);
                        border: 1px solid #C9A45C;
                        border-radius: 14px;
                    }
                    QLabel#TileCaption {
                        color: #8A7A4E;
                        font-size: 12px;
                        font-weight: 600;
                        letter-spacing: 6px;
                    }
                    QLabel#TileFace {
                        color: #16302A;
                        font-size: 54px;
                        font-weight: 900;
                    }
                    QLabel#TileAlt { color: #6E7A66; font-size: 13px; }

                    QLabel#Reason {
                        color: #DCE6DD;
                        padding: 12px 14px;
                        background: rgba(20, 48, 36, 0.65);
                        border: 1px solid #2F5A47;
                        border-radius: 10px;
                    }

                    QToolButton#SectionHeader {
                        text-align: left;
                        padding: 9px 12px;
                        color: #F2C572;
                        font-size: 14px;
                        font-weight: 700;
                        background: rgba(20, 48, 36, 0.7);
                        border: 1px solid #2F5A47;
                        border-radius: 10px;
                    }
                    QToolButton#SectionHeader:hover { border-color: #C9A45C; }

                    QPushButton {
                        background: #1C4434;
                        border: 1px solid #356A51;
                        border-radius: 9px;
                        padding: 8px 12px;
                        color: #EAF2EB;
                    }
                    QPushButton:hover { background: #235140; border-color: #C9A45C; }
                    QPushButton:pressed { background: #163528; }
                    QPushButton#Primary {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #F2C572, stop:1 #D9A748);
                        border: 1px solid #C9A45C;
                        color: #1A2C16;
                        font-size: 16px;
                        font-weight: 800;
                        padding: 12px;
                    }
                    QPushButton#Primary:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #F7D08A, stop:1 #E6B860);
                    }
                    QPushButton#Primary:pressed {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #D9A748, stop:1 #C99A3E);
                    }

                    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
                        background: rgba(11, 28, 21, 0.8);
                        border: 1px solid #2F5A47;
                        border-radius: 9px;
                        color: #EEF2EA;
                        padding: 6px 8px;
                        selection-background-color: #C9A45C;
                        selection-color: #16302A;
                    }
                    QLineEdit:focus, QComboBox:focus { border-color: #F2C572; }
                    QComboBox::drop-down { border: none; width: 22px; }
                    QComboBox QAbstractItemView {
                        background: #102A20;
                        border: 1px solid #2F5A47;
                        selection-background-color: #1C4434;
                        color: #EEF2EA;
                    }

                    QProgressBar {
                        background: rgba(11, 28, 21, 0.8);
                        border: 1px solid #2F5A47;
                        border-radius: 8px;
                        min-height: 16px;
                        text-align: center;
                        color: #16302A;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QProgressBar::chunk {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #D9A748, stop:1 #F2C572);
                        border-radius: 7px;
                    }

                    QTabWidget::pane {
                        background: rgba(11, 28, 21, 0.8);
                        border: 1px solid #2F5A47;
                        border-radius: 10px;
                        top: -1px;
                    }
                    QTabBar::tab {
                        background: rgba(20, 48, 36, 0.6);
                        color: #9DB3A5;
                        padding: 8px 16px;
                        border: 1px solid #2F5A47;
                        border-bottom: none;
                        border-top-left-radius: 9px;
                        border-top-right-radius: 9px;
                        margin-right: 4px;
                    }
                    QTabBar::tab:selected { color: #F2C572; background: #1C4434; }

                    QScrollBar:vertical {
                        background: transparent; width: 10px; margin: 2px;
                    }
                    QScrollBar::handle:vertical {
                        background: #356A51; border-radius: 5px; min-height: 24px;
                    }
                    QScrollBar::handle:vertical:hover { background: #C9A45C; }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
                    QMessageBox { background: #102A20; }
                    """
                )

            def _update_status(self, status: str) -> None:
                ready = "模板已加载" if self.recognizer.is_ready() else "未采集模板"
                self.status_label.setText(f"{status} · {ready}")

            def pick_game_area(self) -> None:
                self._pick_and_store("game_area")

            def pick_region(self, region_key: str) -> None:
                self._pick_and_store(region_key)

            def _pick_and_store(self, region_key: str) -> None:
                picker = RegionPicker(qt, f"框选 {region_key}")
                picker.region_selected.connect(lambda region: self._store_region(region_key, region))
                picker.exec()

            def _store_region(self, region_key: str, region: Region) -> None:
                if region_key == "game_area":
                    self.region_config.game_area = region
                elif region_key in ("hand", "drawn_tile", "self_melds", "dingque", "turn_timer", "self_info", "center_discards"):
                    setattr(self.region_config, region_key, region)
                elif region_key.startswith("opponent_discards."):
                    seat = region_key.split(".", 1)[1]
                    self.region_config.opponent_discards[seat] = region
                elif region_key.startswith("opponent_melds."):
                    seat = region_key.split(".", 1)[1]
                    self.region_config.opponent_melds[seat] = region
                save_region_config(self.region_config)
                self._update_status(f"已保存 {region_key}")

            def capture_and_analyze(self) -> None:
                try:
                    self.latest_screenshot = capture_region(self.region_config.game_area)
                    state = self.recognizer.recognize_game_state(
                        self.latest_screenshot,
                        self.region_config,
                    )
                    self.latest_state = state
                    result = recommend_discard(state, self.rules)
                    save_run_record(self.latest_screenshot, state, result)
                    self._render_result(state, result)
                except Exception as exc:
                    QMessageBox.warning(self, "截图识别失败", str(exc))
                    self._update_status("失败")

            def analyze_manual(self) -> None:
                missing_map = {"未知": None, "万": "m", "筒": "p", "条": "s"}
                try:
                    state = GameState.from_dict(
                        {
                            "missing_suit": missing_map[self.manual_missing.currentText()],
                            "hand": self.manual_hand.text().split(),
                            "recognition_confidence": 1.0,
                        }
                    )
                    self.latest_state = state
                    result = recommend_discard(state, self.rules)
                    save_run_record(None, state, result)
                    self._render_result(state, result)
                except Exception as exc:
                    QMessageBox.warning(self, "手动分析失败", str(exc))

            def save_latest_record(self) -> None:
                result = recommend_discard(self.latest_state, self.rules)
                path = save_run_record(self.latest_screenshot, self.latest_state, result)
                self._update_status(f"已保存 {path.name}")

            def init_templates(self) -> None:
                paths = ensure_template_dirs()
                self._update_status(f"已创建 {len(paths)} 个模板目录")
                QMessageBox.information(
                    self,
                    "模板目录已准备好",
                    "已在 samples/templates 下创建 1m 到 9s 的目录。\n"
                    "把对应牌的小图放进对应目录后，重启应用即可加载模板。",
                )

            def toggle_compact(self) -> None:
                self._compact = not self._compact
                if self._compact:
                    self.resize(460, 180)
                else:
                    self.resize(460, 680)

            def _render_result(self, state, result) -> None:
                tile_text = tile_label(result.recommended_discard) if result.recommended_discard else "--"
                self.recommend_label.setText(tile_text)
                alternatives = "、".join(tile_label(tile) for tile in result.alternatives) or "无"
                self.alt_label.setText(f"备选：{alternatives}")
                self.confidence_bar.setValue(int(round(result.confidence * 100)))
                self.reason_label.setText(result.reason)
                self.route_text.setText(
                    "当前路线：\n"
                    + "\n".join(f"• {route}" for route in result.route)
                    + "\n\n风险提示：\n"
                    + ("\n".join(f"• {note}" for note in result.risk_notes) or "• 暂无")
                )
                self.detail_text.setPlainText(
                    json.dumps(
                        {
                            "state": state.to_dict(),
                            "recommendation": result.to_dict(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                self._update_status("已分析")

        return _CoachWindow()
