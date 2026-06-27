from pathlib import Path

ROOT = Path(__file__).resolve().parent

editor_path = ROOT / "hps_qt" / "dialogs" / "production_plan_editor.py"
editor_path.parent.mkdir(parents=True, exist_ok=True)

editor_path.write_text(r'''
from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QWidget, QFormLayout, QLineEdit, QGroupBox
)
from PySide6.QtCore import Qt


class ProductionPlanEditorDialog(QDialog):
    """
    V25 Production Plan Editor.

    Purpose:
    Review the generated production plan BEFORE creating/replacing project data.
    This is a permanent architecture piece, not a Cannae-specific tool.
    """

    def __init__(self, plan: dict, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.approved = False

        self.setWindowTitle("V25 — Production Plan Review")
        self.resize(1400, 850)

        root = QVBoxLayout(self)

        header = QLabel("Production Plan Review")
        header.setStyleSheet("font-size:22pt;font-weight:bold;")
        root.addWidget(header)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        self.scene_tree = QTreeWidget()
        self.scene_tree.setHeaderLabels(["Scene / Block", "Runtime", "Characters / Tags"])
        splitter.addWidget(self.scene_tree)

        center = QWidget()
        center_layout = QVBoxLayout(center)

        self.detail_title = QLabel("Select a scene or block")
        self.detail_title.setStyleSheet("font-size:16pt;font-weight:bold;")
        center_layout.addWidget(self.detail_title)

        self.detail_text = QTextEdit()
        center_layout.addWidget(self.detail_text, 2)

        cue_box = QGroupBox("Production Cues")
        cue_layout = QFormLayout(cue_box)

        self.character_field = QLineEdit()
        self.duration_field = QLineEdit()
        self.locations_field = QLineEdit()
        self.equipment_field = QLineEdit()
        self.sfx_field = QLineEdit()
        self.ambience_field = QLineEdit()

        cue_layout.addRow("Character", self.character_field)
        cue_layout.addRow("Duration", self.duration_field)
        cue_layout.addRow("Locations", self.locations_field)
        cue_layout.addRow("Equipment", self.equipment_field)
        cue_layout.addRow("SFX", self.sfx_field)
        cue_layout.addRow("Ambience", self.ambience_field)

        center_layout.addWidget(cue_box)

        self.image_prompt = QTextEdit()
        self.image_prompt.setPlaceholderText("Image prompt")
        center_layout.addWidget(QLabel("Image Prompt"))
        center_layout.addWidget(self.image_prompt, 1)

        self.music_cue = QTextEdit()
        self.music_cue.setPlaceholderText("Music cue")
        center_layout.addWidget(QLabel("Music Cue"))
        center_layout.addWidget(self.music_cue, 1)

        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel("Metrics / Validation"))

        self.metrics_table = QTableWidget(0, 2)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "Value"])
        right_layout.addWidget(self.metrics_table)

        self.raw_json = QTextEdit()
        self.raw_json.setReadOnly(True)
        right_layout.addWidget(QLabel("Raw JSON"))
        right_layout.addWidget(self.raw_json, 1)

        splitter.addWidget(right)
        splitter.setSizes([360, 720, 320])

        buttons = QHBoxLayout()
        self.approve_btn = QPushButton("Approve Production Plan")
        self.close_btn = QPushButton("Cancel")
        buttons.addWidget(self.approve_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self.scene_tree.itemSelectionChanged.connect(self.on_selection)
        self.approve_btn.clicked.connect(self.approve)
        self.close_btn.clicked.connect(self.reject)

        self.populate()

    def populate(self):
        scenes = self.plan.get("scenes", [])
        blocks = [b for s in scenes for b in s.get("blocks", [])]
        runtime = sum(int(b.get("duration_seconds", 0)) for b in blocks)

        self.summary.setText(
            f"Scenes: {len(scenes)} | Blocks: {len(blocks)} | "
            f"Runtime: {runtime / 60:.1f} min | "
            f"Characters: {len(self.plan.get('characters', []))} | "
            f"Voice cost: ${self.plan.get('estimated_voice_cost', 0.0):.2f}"
        )

        self.scene_tree.clear()

        for scene in scenes:
            scene_blocks = scene.get("blocks", [])
            scene_seconds = sum(int(b.get("duration_seconds", 0)) for b in scene_blocks)
            scene_item = QTreeWidgetItem([
                f"{scene.get('id', '')} — {scene.get('title', '')}",
                f"{scene_seconds / 60:.1f} min",
                ", ".join(scene.get("locations", [])[:4])
            ])
            scene_item.setData(0, Qt.UserRole, {"type": "scene", "data": scene})
            self.scene_tree.addTopLevelItem(scene_item)

            for block in scene_blocks:
                tags = []
                if block.get("character"):
                    tags.append(block.get("character"))
                tags += block.get("locations", [])[:2]

                b_item = QTreeWidgetItem([
                    f"{block.get('id', '')}",
                    f"{int(block.get('duration_seconds', 0))} sec",
                    ", ".join(tags)
                ])
                b_item.setData(0, Qt.UserRole, {"type": "block", "data": block})
                scene_item.addChild(b_item)

        self.scene_tree.expandToDepth(0)
        self.populate_metrics()
        self.raw_json.setPlainText(json.dumps(self.plan, indent=2, ensure_ascii=False))

    def populate_metrics(self):
        scenes = self.plan.get("scenes", [])
        blocks = [b for s in scenes for b in s.get("blocks", [])]

        locations = sorted(set(x for b in blocks for x in b.get("locations", [])))
        equipment = sorted(set(x for b in blocks for x in b.get("equipment", [])))
        sfx = sorted(set(x for b in blocks for x in b.get("sfx", [])))
        ambience = sorted(set(x for b in blocks for x in b.get("ambience", [])))
        runtime = sum(int(b.get("duration_seconds", 0)) for b in blocks)

        rows = [
            ("Scenes", len(scenes)),
            ("Blocks", len(blocks)),
            ("Runtime", f"{runtime / 60:.1f} min"),
            ("Characters", len(self.plan.get("characters", []))),
            ("Locations", len(locations)),
            ("Equipment tags", len(equipment)),
            ("SFX cues", len(sfx)),
            ("Ambience cues", len(ambience)),
            ("Image prompts", len(blocks)),
            ("Music cues", len(blocks)),
            ("Voice cost only", f"${self.plan.get('estimated_voice_cost', 0.0):.2f}"),
            ("Images/music/analysis cost", "$0.00"),
            ("Validation", "OK" if self.plan.get("validation", {}).get("ok", True) else "Warnings"),
        ]

        self.metrics_table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.metrics_table.setItem(r, 0, QTableWidgetItem(str(k)))
            self.metrics_table.setItem(r, 1, QTableWidgetItem(str(v)))

    def on_selection(self):
        items = self.scene_tree.selectedItems()
        if not items:
            return

        payload = items[0].data(0, Qt.UserRole) or {}
        typ = payload.get("type")
        data = payload.get("data") or {}

        if typ == "scene":
            self.detail_title.setText(f"{data.get('id', '')} — {data.get('title', '')}")
            self.detail_text.setPlainText(data.get("summary", ""))
            self.character_field.setText("")
            self.duration_field.setText(
                f"{sum(int(b.get('duration_seconds', 0)) for b in data.get('blocks', []))} sec"
            )
            self.locations_field.setText(", ".join(data.get("locations", [])))
            self.equipment_field.setText(", ".join(data.get("equipment", [])))
            self.sfx_field.setText("")
            self.ambience_field.setText("")
            self.image_prompt.setPlainText("")
            self.music_cue.setPlainText("")

        elif typ == "block":
            self.detail_title.setText(data.get("id", "Block"))
            self.detail_text.setPlainText(data.get("text", ""))
            self.character_field.setText(data.get("character", ""))
            self.duration_field.setText(str(data.get("duration_seconds", "")))
            self.locations_field.setText(", ".join(data.get("locations", [])))
            self.equipment_field.setText(", ".join(data.get("equipment", [])))
            self.sfx_field.setText(", ".join(data.get("sfx", [])))
            self.ambience_field.setText(", ".join(data.get("ambience", [])))
            self.image_prompt.setPlainText(data.get("image_prompt", ""))
            self.music_cue.setPlainText(data.get("music_cue", ""))

    def approve(self):
        self.approved = True
        self.accept()
''', encoding="utf-8")


wizard = ROOT / "hps_qt" / "dialogs" / "project_wizard.py"
w = wizard.read_text(encoding="utf-8")

if "from hps_qt.dialogs.production_plan_editor import ProductionPlanEditorDialog" not in w:
    w = w.replace(
        "from hps.core.analysis.analyzer import GenericScriptAnalyzer, plan_metrics, plan_to_legacy_importer_shape\n",
        "from hps.core.analysis.analyzer import GenericScriptAnalyzer, plan_metrics, plan_to_legacy_importer_shape\n"
        "from hps_qt.dialogs.production_plan_editor import ProductionPlanEditorDialog\n"
    )

# Add review button if missing
if "self.review_btn" not in w:
    w = w.replace(
        '        self.generate_btn = QPushButton("Generate Project")\n        self.generate_btn.setEnabled(False)',
        '        self.review_btn = QPushButton("Review Production Plan")\n        self.review_btn.setEnabled(False)\n        self.generate_btn = QPushButton("Generate Project")\n        self.generate_btn.setEnabled(False)'
    )

    w = w.replace(
        "        actions.addWidget(self.analyze_btn)\n        actions.addWidget(self.generate_btn)",
        "        actions.addWidget(self.analyze_btn)\n        actions.addWidget(self.review_btn)\n        actions.addWidget(self.generate_btn)"
    )

    w = w.replace(
        "        self.analyze_btn.clicked.connect(self.analyze_script)\n        self.generate_btn.clicked.connect(self.generate_project)",
        "        self.analyze_btn.clicked.connect(self.analyze_script)\n        self.review_btn.clicked.connect(self.review_plan)\n        self.generate_btn.clicked.connect(self.generate_project)"
    )

# Enable review button after analysis
w = w.replace(
    "        self.populate_preview(plan)\n        self.generate_btn.setEnabled(True)",
    "        self.populate_preview(plan)\n        self.review_btn.setEnabled(True)\n        self.generate_btn.setEnabled(False)"
)

# Add review_plan method before generate_project
marker = "    def generate_project(self):"
method = r'''    def review_plan(self):
        if not self.plan:
            QMessageBox.warning(self, "No analysis", "Analyze the script first.")
            return

        dlg = ProductionPlanEditorDialog(self.plan, self)
        if dlg.exec() and getattr(dlg, "approved", False):
            self.generate_btn.setEnabled(True)
            QMessageBox.information(
                self,
                "Production Plan Approved",
                "Production plan approved. You can now generate the project."
            )

'''
if "def review_plan(self):" not in w:
    w = w.replace(marker, method + marker)

wizard.write_text(w, encoding="utf-8")


doc = ROOT / "docs" / "V25_PRODUCTION_PLAN_EDITOR.md"
doc.write_text("""# V25 Production Plan Editor

Adds a permanent review step between analysis and project generation.

Flow:

1. Import/paste script
2. Analyze
3. Review Production Plan
4. Approve Production Plan
5. Generate Project

This prevents accidental project replacement and gives the user a scene/block level view before generation.

The editor shows:

- scene tree
- blocks
- runtime
- characters/tags
- narration text
- image prompts
- music cues
- SFX
- ambience
- cost summary

No paid AI is used.
""", encoding="utf-8")

print("V25 Production Plan Editor installed.")
print("Run: .\\run_studio_v24.bat")