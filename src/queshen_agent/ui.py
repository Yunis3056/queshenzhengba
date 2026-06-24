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
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QTabWidget,
            QTextEdit,
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
        "QGridLayout": QGridLayout,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPushButton": QPushButton,
        "QPlainTextEdit": QPlainTextEdit,
        "QTabWidget": QTabWidget,
        "QTextEdit": QTextEdit,
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
                root = QWidget()
                layout = QVBoxLayout(root)
                layout.setContentsMargins(16, 16, 16, 16)
                layout.setSpacing(12)

                header = QHBoxLayout()
                title = QLabel("雀神争霸 AI 教练")
                title.setObjectName("Title")
                self.status_label = QLabel("")
                self.status_label.setObjectName("Status")
                header.addWidget(title)
                header.addStretch()
                header.addWidget(self.status_label)
                layout.addLayout(header)

                self.recommend_label = QLabel("建议打：--")
                self.recommend_label.setObjectName("Recommend")
                layout.addWidget(self.recommend_label)

                self.reason_label = QLabel("先选择游戏区域并校准牌区。")
                self.reason_label.setWordWrap(True)
                self.reason_label.setObjectName("Reason")
                layout.addWidget(self.reason_label)

                controls = QGridLayout()
                controls.setSpacing(8)
                buttons = [
                    ("选择游戏区域", self.pick_game_area),
                    ("校准手牌区", lambda: self.pick_region("hand")),
                    ("校准待打牌", lambda: self.pick_region("drawn_tile")),
                    ("校准自己碰杠", lambda: self.pick_region("self_melds")),
                    ("校准倒计时", lambda: self.pick_region("turn_timer")),
                    ("一键截图识别", self.capture_and_analyze),
                    ("初始化模板目录", self.init_templates),
                ]
                for index, (text, handler) in enumerate(buttons):
                    button = QPushButton(text)
                    button.clicked.connect(handler)
                    controls.addWidget(button, index // 2, index % 2)
                layout.addLayout(controls)

                opponent_box = QFrame()
                opponent_box.setObjectName("Panel")
                opponent_layout = QGridLayout(opponent_box)
                opponent_layout.addWidget(QLabel("对手区域校准"), 0, 0, 1, 3)
                for col, seat in enumerate(("left", "top", "right")):
                    discard_button = QPushButton(f"{seat} 弃牌")
                    discard_button.clicked.connect(lambda checked=False, s=seat: self.pick_region(f"opponent_discards.{s}"))
                    meld_button = QPushButton(f"{seat} 碰杠")
                    meld_button.clicked.connect(lambda checked=False, s=seat: self.pick_region(f"opponent_melds.{s}"))
                    opponent_layout.addWidget(discard_button, 1, col)
                    opponent_layout.addWidget(meld_button, 2, col)
                layout.addWidget(opponent_box)

                manual = QFrame()
                manual.setObjectName("Panel")
                manual_layout = QGridLayout(manual)
                manual_layout.addWidget(QLabel("手动兜底输入"), 0, 0, 1, 2)
                self.manual_missing = QComboBox()
                self.manual_missing.addItems(["未知", "万", "筒", "条"])
                self.manual_hand = QLineEdit()
                self.manual_hand.setPlaceholderText("例如：1m 2m 3m 5p 5p 8s")
                manual_button = QPushButton("用手动牌面分析")
                manual_button.clicked.connect(self.analyze_manual)
                manual_layout.addWidget(QLabel("定缺"), 1, 0)
                manual_layout.addWidget(self.manual_missing, 1, 1)
                manual_layout.addWidget(self.manual_hand, 2, 0, 1, 2)
                manual_layout.addWidget(manual_button, 3, 0, 1, 2)
                layout.addWidget(manual)

                record_row = QHBoxLayout()
                save_button = QPushButton("保存样本")
                save_button.clicked.connect(self.save_latest_record)
                collapse_button = QPushButton("折叠/展开")
                collapse_button.clicked.connect(self.toggle_compact)
                record_row.addWidget(save_button)
                record_row.addWidget(collapse_button)
                layout.addLayout(record_row)

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
                    QMainWindow, QWidget {
                        background: #111318;
                        color: #F4F1E8;
                        font-family: "Microsoft YaHei UI", "Segoe UI";
                        font-size: 14px;
                    }
                    QLabel#Title {
                        font-size: 20px;
                        font-weight: 700;
                    }
                    QLabel#Status {
                        color: #8EA0B8;
                        font-size: 12px;
                    }
                    QLabel#Recommend {
                        color: #F2C572;
                        font-size: 30px;
                        font-weight: 800;
                        padding: 14px 16px;
                        background: #1B1F27;
                        border: 1px solid #2A303A;
                        border-radius: 8px;
                    }
                    QLabel#Reason {
                        color: #D8DEE9;
                        line-height: 1.5;
                        padding: 12px;
                        background: #171B22;
                        border: 1px solid #2A303A;
                        border-radius: 8px;
                    }
                    QFrame#Panel {
                        background: #1B1F27;
                        border: 1px solid #2A303A;
                        border-radius: 8px;
                    }
                    QPushButton {
                        background: #252B36;
                        border: 1px solid #36404F;
                        border-radius: 8px;
                        padding: 8px 10px;
                        color: #F4F1E8;
                    }
                    QPushButton:hover {
                        background: #303849;
                        border-color: #F2C572;
                    }
                    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QTabWidget::pane {
                        background: #171B22;
                        border: 1px solid #2A303A;
                        border-radius: 8px;
                        color: #F4F1E8;
                        padding: 6px;
                    }
                    QTabBar::tab {
                        background: #1B1F27;
                        color: #AAB6C6;
                        padding: 8px 12px;
                        border-top-left-radius: 8px;
                        border-top-right-radius: 8px;
                    }
                    QTabBar::tab:selected {
                        color: #F2C572;
                        background: #252B36;
                    }
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
                self.recommend_label.setText(f"建议打：{tile_text}")
                alternatives = "、".join(tile_label(tile) for tile in result.alternatives) or "无"
                self.reason_label.setText(
                    f"{result.reason}\n备选：{alternatives} · 置信度：{result.confidence:.0%}"
                )
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
