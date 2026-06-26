"""
Assembly Engine Panel — V23
Qt widget for the Assembly Engine tab under Project workspace.
"""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QTextEdit, QSizePolicy, QProgressBar
)

from hps.core.assembly_engine import AssemblyEngine


# ------------------------------------------------------------------ #
#  Background worker so the UI stays responsive
# ------------------------------------------------------------------ #

class BuildWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, db):
        super().__init__()
        self.db = db

    def run(self):
        try:
            engine = AssemblyEngine(self.db)
            result = engine.build_all()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ------------------------------------------------------------------ #
#  Main panel
# ------------------------------------------------------------------ #

class AssemblyEnginePanel(QWidget):
    """
    V23 — Assembly Engine Panel.
    Exposed under Project → Assembly Engine.
    """

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        self._result = None
        self._worker = None

        if self.state is not None:
            self.state.project_changed.connect(self._on_project_changed)

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Title
        title = QLabel("Assembly Engine")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Reads approved voice / image / music → builds timeline → exports package + FFmpeg script."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #aaa; font-size: 0.9em;")
        layout.addWidget(subtitle)

        # ---- Buttons ----
        btn_row = QHBoxLayout()
        self.btn_build = QPushButton("⚙ Build Timeline Plan")
        self.btn_export = QPushButton("📦 Export Assembly Package")
        self.btn_preview = QPushButton("🌐 Open Preview HTML")
        self.btn_folder = QPushButton("📂 Open Assembly Folder")
        self.btn_ffmpeg = QPushButton("🎬 Open FFmpeg Script")

        for btn in (self.btn_build, self.btn_export, self.btn_preview, self.btn_folder, self.btn_ffmpeg):
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        self.btn_build.clicked.connect(self._run_build_all)
        self.btn_export.clicked.connect(self._run_build_all)   # same action, kept separate for clarity
        self.btn_preview.clicked.connect(self._open_preview)
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_ffmpeg.clicked.connect(self._open_ffmpeg)

        # ---- Progress bar (hidden by default) ----
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ---- Summary label ----
        self.summary_label = QLabel("No assembly built yet. Click 'Build Timeline Plan'.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #ccc; padding: 4px;")
        layout.addWidget(self.summary_label)

        # ---- Timeline table ----
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "#", "Block", "Scene", "Ready", "Start", "Duration", "Voice", "Image", "Music"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # ---- Log ----
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.setStyleSheet("font-size: 0.82em; color: #aaa;")
        layout.addWidget(self.log)

        self._set_buttons_enabled(False)

    # ------------------------------------------------------------------ #
    #  State management
    # ------------------------------------------------------------------ #

    def _on_project_changed(self, db):
        self.db = db
        self._result = None
        self._set_buttons_enabled(True)
        self.summary_label.setText("Project loaded. Click 'Build Timeline Plan' to begin.")
        self.table.setRowCount(0)
        self.log.clear()

    def _set_buttons_enabled(self, enabled):
        for btn in (self.btn_build, self.btn_export, self.btn_preview, self.btn_folder, self.btn_ffmpeg):
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------ #
    #  Build
    # ------------------------------------------------------------------ #

    def _run_build_all(self):
        if not self.db:
            QMessageBox.warning(self, "No Project", "Open a project first.")
            return

        self._set_buttons_enabled(False)
        self.progress.setVisible(True)
        self.summary_label.setText("Building assembly…")
        self.log.append("Starting assembly build…")

        self._worker = BuildWorker(self.db)
        self._worker.finished.connect(self._on_build_done)
        self._worker.error.connect(self._on_build_error)
        self._worker.start()

    def _on_build_done(self, result):
        self.progress.setVisible(False)
        self._set_buttons_enabled(True)
        self._result = result
        timeline = result["timeline"]

        # Summary
        summary = result["summary"]
        if isinstance(summary, Path) and summary.exists():
            import json
            summary = json.loads(summary.read_text(encoding="utf-8"))

        if isinstance(summary, dict):
            self.summary_label.setText(
                f"Blocks: {summary.get('total_blocks', '?')}  |  "
                f"Ready: {summary.get('ready_blocks', '?')}  |  "
                f"Complete: {summary.get('complete_blocks', '?')}  |  "
                f"Duration: {summary.get('total_duration_minutes', '?'):.1f} min"
            )

        # Populate table
        self._populate_table(timeline)

        out = result["out_dir"]
        self.log.append(f"✔ Build complete. Output: {out}")
        self.log.append(f"  timeline.json  preview.html  render_episode_ffmpeg.bat")

    def _on_build_error(self, msg):
        self.progress.setVisible(False)
        self._set_buttons_enabled(True)
        self.log.append(f"✘ Error: {msg}")
        QMessageBox.critical(self, "Assembly Error", msg)

    # ------------------------------------------------------------------ #
    #  Table population
    # ------------------------------------------------------------------ #

    def _populate_table(self, timeline):
        self.table.setRowCount(0)
        self.table.setRowCount(len(timeline))

        def item(text, color=None):
            it = QTableWidgetItem(str(text))
            it.setTextAlignment(Qt.AlignCenter)
            if color:
                it.setForeground(color)
            return it

        from PySide6.QtGui import QColor
        green = QColor("#2ecc71")
        red = QColor("#e74c3c")
        yellow = QColor("#f1c40f")

        for row, entry in enumerate(timeline):
            self.table.setItem(row, 0, item(entry["sequence"]))
            self.table.setItem(row, 1, item(entry["block_id"]))
            self.table.setItem(row, 2, QTableWidgetItem(entry["scene"]))

            ready_text = "✔ READY" if entry["ready"] else ("⚠ NO MUSIC" if not entry["missing"] or entry["missing"] == ["music"] else "✘ NOT READY")
            ready_color = green if entry["ready"] else (yellow if entry["missing"] == ["music"] else red)
            self.table.setItem(row, 3, item(ready_text, ready_color))

            self.table.setItem(row, 4, item(f"{entry['start_seconds']:.1f}s"))
            self.table.setItem(row, 5, item(f"{entry['duration_seconds']:.1f}s"))

            voice_text = "✔" if entry["voice"] else "✘ missing"
            self.table.setItem(row, 6, item(voice_text, green if entry["voice"] else red))

            image_text = "✔" if entry["image"] else "✘ missing"
            self.table.setItem(row, 7, item(image_text, green if entry["image"] else red))

            music_text = "✔" if entry["music"] else "—"
            self.table.setItem(row, 8, item(music_text, green if entry["music"] else yellow))

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------ #
    #  Button actions
    # ------------------------------------------------------------------ #

    def _open_preview(self):
        if not self._result:
            QMessageBox.information(self, "Build First", "Run 'Build Timeline Plan' first.")
            return
        p = self._result.get("preview_html")
        if p and Path(p).exists():
            os.startfile(str(p))
        else:
            QMessageBox.warning(self, "Not Found", "preview.html not found. Run build first.")

    def _open_folder(self):
        out = self._result.get("out_dir") if self._result else None
        if not out:
            if self.db:
                out = self.db.root_dir / "exports" / "assembly_engine"
                out.mkdir(parents=True, exist_ok=True)
            else:
                QMessageBox.warning(self, "No Project", "Open a project first.")
                return
        try:
            os.startfile(str(out))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _open_ffmpeg(self):
        if not self._result:
            QMessageBox.information(self, "Build First", "Run 'Build Timeline Plan' first.")
            return
        p = self._result.get("ffmpeg_script")
        if p and Path(p).exists():
            try:
                os.startfile(str(p))
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
        else:
            QMessageBox.warning(self, "Not Found", "FFmpeg script not found. Run build first.")
