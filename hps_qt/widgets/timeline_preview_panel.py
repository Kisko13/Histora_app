"""
Timeline Preview Panel — V24
Visual horizontal timeline inspector.
Reads from exports/assembly_engine/timeline.json, or builds in-memory via AssemblyEngine.
Shows every block as a colour-coded rectangle. Clicking a block selects it in the main app.
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QFrame, QMessageBox, QSplitter
)

# ------------------------------------------------------------------ #
#  Colour scheme — matches block readiness state
# ------------------------------------------------------------------ #
COLOR_COMPLETE  = QColor("#2ecc71")   # green  — voice + image + music
COLOR_READY     = QColor("#f39c12")   # amber  — voice + image, no music
COLOR_NO_VOICE  = QColor("#e74c3c")   # red    — missing voice or image
COLOR_SELECTED  = QColor("#4cc2ff")   # blue highlight
COLOR_TEXT      = QColor("#ffffff")
COLOR_BG        = QColor("#1a1a2e")
COLOR_RULER     = QColor("#2a2a4a")
COLOR_RULER_TXT = QColor("#888888")

BLOCK_HEIGHT   = 80   # px
RULER_HEIGHT   = 24   # px
MIN_BLOCK_W    = 60   # px minimum width so label is readable
PX_PER_SECOND  = 8    # zoom: pixels per second of audio


# ------------------------------------------------------------------ #
#  Timeline canvas widget
# ------------------------------------------------------------------ #

class TimelineCanvas(QWidget):
    """
    Renders the horizontal timeline as a painted widget.
    Emits block_clicked(block_id) when the user clicks a block.
    """
    block_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []          # list of timeline dicts from AssemblyEngine
        self._selected_id = None
        self.setMinimumHeight(RULER_HEIGHT + BLOCK_HEIGHT + 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover_id = None

    def load(self, items: list):
        self._items = items
        self._selected_id = None
        self._recalc_size()
        self.update()

    def select(self, block_id: str):
        self._selected_id = block_id
        self.update()

    def _recalc_size(self):
        if not self._items:
            self.setMinimumWidth(400)
            return
        total_s = self._items[-1]["end_seconds"] if self._items else 0
        w = max(400, int(total_s * PX_PER_SECOND) + 40)
        self.setMinimumWidth(w)

    def _block_rect(self, item) -> QRectF:
        x = item["start_seconds"] * PX_PER_SECOND + 4
        w = max(MIN_BLOCK_W, item["duration_seconds"] * PX_PER_SECOND - 4)
        y = RULER_HEIGHT + 4
        return QRectF(x, y, w, BLOCK_HEIGHT - 8)

    def _color_for(self, item) -> QColor:
        if item["block_id"] == self._selected_id:
            return COLOR_SELECTED
        if item["complete"]:
            return COLOR_COMPLETE
        if item["ready"]:
            return COLOR_READY
        return COLOR_NO_VOICE

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_BG)

        # Ruler
        painter.fillRect(0, 0, self.width(), RULER_HEIGHT, COLOR_RULER)
        painter.setPen(QPen(COLOR_RULER_TXT))
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        total_s = self._items[-1]["end_seconds"] if self._items else 60
        step = 10 if total_s < 300 else 30
        for t in range(0, int(total_s) + step, step):
            x = int(t * PX_PER_SECOND) + 4
            painter.drawLine(x, 16, x, RULER_HEIGHT)
            mins = t // 60
            secs = t % 60
            painter.drawText(x + 2, 14, f"{mins}:{secs:02d}")

        if not self._items:
            painter.setPen(QColor("#666"))
            painter.drawText(20, RULER_HEIGHT + 40, "No timeline loaded. Click 'Load Timeline'.")
            return

        # Blocks
        label_font = QFont("Segoe UI", 8, QFont.Bold)
        sub_font   = QFont("Segoe UI", 7)
        painter.setFont(label_font)

        for item in self._items:
            rect  = self._block_rect(item)
            color = self._color_for(item)

            # Hover darken
            if item["block_id"] == self._hover_id and item["block_id"] != self._selected_id:
                color = color.darker(115)

            # Fill
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(150), 1))
            painter.drawRoundedRect(rect, 4, 4)

            # Text
            painter.setPen(QPen(COLOR_TEXT))
            painter.setFont(label_font)
            line1 = item["block_id"]
            painter.drawText(int(rect.x()) + 6, int(rect.y()) + 16, line1)

            painter.setFont(sub_font)
            line2 = f"{item['duration_seconds']:.1f}s"
            painter.drawText(int(rect.x()) + 6, int(rect.y()) + 30, line2)

            missing = item.get("missing", [])
            if missing:
                painter.setPen(QColor("#ffdddd"))
                line3 = "✘ " + ", ".join(missing)
            else:
                painter.setPen(QColor("#ccffcc"))
                line3 = "✔ READY"
            painter.drawText(int(rect.x()) + 6, int(rect.y()) + 44, line3)

            scene = (item.get("scene") or "")[:18]
            painter.setPen(QColor("#ddd"))
            painter.drawText(int(rect.x()) + 6, int(rect.y()) + 58, scene)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for item in self._items:
                if self._block_rect(item).contains(event.position()):
                    self._selected_id = item["block_id"]
                    self.update()
                    self.block_clicked.emit(item["block_id"])
                    return

    def mouseMoveEvent(self, event):
        prev = self._hover_id
        self._hover_id = None
        for item in self._items:
            if self._block_rect(item).contains(event.position()):
                self._hover_id = item["block_id"]
                break
        if self._hover_id != prev:
            self.update()


# ------------------------------------------------------------------ #
#  Main panel
# ------------------------------------------------------------------ #

class TimelinePreviewPanel(QWidget):
    """
    V24 — Timeline Preview Panel.
    Shown under Project → Timeline Preview.
    """
    # Emitted when user clicks a block — main app uses this to select the block
    block_selected = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        self._items = []

        if self.state is not None:
            self.state.project_changed.connect(self._on_project_changed)
            self.state.selected_block_changed.connect(self._on_block_changed)

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Title row
        title = QLabel("Timeline Preview")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Legend
        legend = QHBoxLayout()
        for color, label in [
            (COLOR_COMPLETE, "Complete (voice+image+music)"),
            (COLOR_READY,    "Ready (no music)"),
            (COLOR_NO_VOICE, "Not ready (missing voice/image)"),
            (COLOR_SELECTED, "Selected"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color.name()}; font-size: 14pt;")
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #aaa; font-size: 8pt;")
            legend.addWidget(dot)
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_load    = QPushButton("↺ Load Timeline")
        self.btn_refresh = QPushButton("⟳ Refresh")
        self.lbl_summary = QLabel("No timeline loaded.")
        self.lbl_summary.setStyleSheet("color: #888; font-size: 9pt;")

        for btn in (self.btn_load, self.btn_refresh):
            btn.setFixedHeight(28)
            toolbar.addWidget(btn)
        toolbar.addWidget(self.lbl_summary)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.btn_load.clicked.connect(self._load)
        self.btn_refresh.clicked.connect(self._load)

        # Scrollable canvas
        self.canvas = TimelineCanvas()
        self.canvas.block_clicked.connect(self._on_canvas_block_clicked)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(RULER_HEIGHT + BLOCK_HEIGHT + 30)
        layout.addWidget(scroll)

        # Block detail bar
        self.detail_bar = QLabel("Click a block to see details.")
        self.detail_bar.setStyleSheet(
            "background:#252526; color:#ccc; padding:6px; font-size:9pt; border-top:1px solid #333;"
        )
        self.detail_bar.setWordWrap(True)
        layout.addWidget(self.detail_bar)

    # ------------------------------------------------------------------ #
    #  State
    # ------------------------------------------------------------------ #

    def _on_project_changed(self, db):
        self.db = db
        self._load()

    def _on_block_changed(self, block_id):
        if block_id:
            self.canvas.select(block_id)
            self._show_detail(block_id)

    def _on_canvas_block_clicked(self, block_id):
        self._show_detail(block_id)
        self.block_selected.emit(block_id)

    # ------------------------------------------------------------------ #
    #  Load
    # ------------------------------------------------------------------ #

    def _load(self):
        if not self.db:
            return
        items = self._load_from_file() or self._build_in_memory()
        if items is None:
            return
        self._items = items
        self.canvas.load(items)
        total = items[-1]["end_seconds"] if items else 0
        ready = sum(1 for i in items if i["ready"])
        complete = sum(1 for i in items if i["complete"])
        self.lbl_summary.setText(
            f"{len(items)} blocks  ·  {total/60:.1f} min  ·  "
            f"{ready} ready  ·  {complete} complete"
        )

    def _load_from_file(self):
        """Try reading the pre-built timeline.json from AssemblyEngine output."""
        if not self.db:
            return None
        path = self.db.root_dir / "exports" / "assembly_engine" / "timeline.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _build_in_memory(self):
        """Fall back to building timeline in memory via AssemblyEngine."""
        if not self.db:
            return None
        try:
            from hps.core.assembly_engine import AssemblyEngine
            return AssemblyEngine(self.db).build_timeline()
        except Exception as e:
            self.lbl_summary.setText(f"Error building timeline: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Detail bar
    # ------------------------------------------------------------------ #

    def _show_detail(self, block_id):
        item = next((i for i in self._items if i["block_id"] == block_id), None)
        if not item:
            return
        missing_str = ", ".join(item["missing"]) if item["missing"] else "none"
        status = "✔ COMPLETE" if item["complete"] else ("⚠ READY (no music)" if item["ready"] else "✘ NOT READY")
        self.detail_bar.setText(
            f"  {item['block_id']}  ·  {item['scene']}  ·  {item['character']}  "
            f"·  Start: {item['start_seconds']:.1f}s  ·  Duration: {item['duration_seconds']:.1f}s  "
            f"·  {status}  ·  Missing: {missing_str}"
        )
