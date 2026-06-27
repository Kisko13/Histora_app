
from __future__ import annotations

import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QCheckBox, QTabWidget,
    QWidget, QTableWidget, QTableWidgetItem, QDialogButtonBox, QGroupBox
)

from hps.core.script_importer import ScriptImporter
from hps.core.analysis.models import AnalysisContext
from hps.core.analysis.analyzer import GenericScriptAnalyzer, plan_metrics, plan_to_legacy_importer_shape


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        texts = [t.text or "" for t in p.findall(".//w:t", ns)]
        if texts:
            paragraphs.append("".join(texts))
    return "\n\n".join(paragraphs)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        raise RuntimeError("PDF import needs pypdf. Install with: pip install pypdf")


def read_script_file(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in [".txt", ".md"]:
        return p.read_text(encoding="utf-8", errors="replace")
    if ext == ".docx":
        return _read_docx(p)
    if ext == ".pdf":
        return _read_pdf(p)
    raise RuntimeError(f"Unsupported script file type: {ext}")


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _plan_stats(plan: dict) -> dict:
    stats = plan_metrics(plan)
    stats.setdefault("voice_cost", 0.0)
    stats.setdefault("images", 0)
    stats.setdefault("music_cues", 0)
    stats.setdefault("locations", 0)
    stats.setdefault("equipment", 0)
    stats.setdefault("sfx", 0)
    stats.setdefault("ambience", 0)
    return stats



class ProjectWizardDialog(QDialog):
    """
    V25 Project Creation Wizard.

    This does NOT spend money.
    Analysis uses local Ollama/Qwen if available.
    If Ollama fails, deterministic splitting is used.
    Only later voice generation may use paid/API providers.
    """

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.plan = None
        self.generated = False

        self.setWindowTitle("V25 — New Historical Episode Wizard")
        self.resize(1150, 820)

        root = QVBoxLayout(self)

        title = QLabel("V25 — New Historical Episode")
        title.setStyleSheet("font-size:22pt;font-weight:bold;")
        root.addWidget(title)

        subtitle = QLabel(
            "Import or paste a full script, analyze it locally, preview the production plan, "
            "then generate the project. No paid AI is used here. Voice cost is only estimated."
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form = QFormLayout()
        self.project_title = QLineEdit("Historical POV Project")
        self.period = QLineEdit("Roman Republic")
        self.target_runtime = QLineEdit("75")
        self.voice_style = QLineEdit("Deep restrained male narrator, slow immersive delivery")
        self.main_pov_character = QLineEdit("")
        self.known_characters = QLineEdit("")
        self.known_locations = QLineEdit("")
        self.known_equipment = QLineEdit("")

        self.ollama_model = QLineEdit("qwen2.5:7b")
        self.ollama_host = QLineEdit("http://127.0.0.1:11434")
        self.use_ollama = QCheckBox("Use local Ollama/Qwen if available")
        self.use_ollama.setChecked(True)

        form.addRow("Project title", self.project_title)
        form.addRow("Historical period", self.period)
        form.addRow("Target runtime minutes", self.target_runtime)
        form.addRow("Voice style", self.voice_style)
        form.addRow("Main POV character (optional)", self.main_pov_character)
        form.addRow("Known characters, comma-separated (optional)", self.known_characters)
        form.addRow("Known locations, comma-separated (optional)", self.known_locations)
        form.addRow("Known equipment, comma-separated (optional)", self.known_equipment)
        form.addRow("Ollama model", self.ollama_model)
        form.addRow("Ollama host", self.ollama_host)
        form.addRow("Local AI", self.use_ollama)
        root.addLayout(form)

        import_box = QGroupBox("Script Input")
        import_layout = QVBoxLayout(import_box)

        row = QHBoxLayout()
        self.import_btn = QPushButton("Import Script File (.md .txt .docx .pdf)")
        self.clear_btn = QPushButton("Clear")
        row.addWidget(self.import_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        import_layout.addLayout(row)

        self.script_text = QTextEdit()
        self.script_text.setPlaceholderText("Paste full narration script here...")
        import_layout.addWidget(self.script_text, 1)
        root.addWidget(import_box, 2)

        actions = QHBoxLayout()
        self.analyze_btn = QPushButton("Analyze Script")
        self.generate_btn = QPushButton("Generate Project")
        self.generate_btn.setEnabled(False)
        self.close_btn = QPushButton("Close")
        actions.addWidget(self.analyze_btn)
        actions.addWidget(self.generate_btn)
        actions.addStretch()
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.tabs = QTabWidget()
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)

        self.scene_table = QTableWidget(0, 6)
        self.scene_table.setHorizontalHeaderLabels(["Scene", "Title", "Blocks", "Words", "Runtime", "Summary"])

        self.character_table = QTableWidget(0, 3)
        self.character_table.setHorizontalHeaderLabels(["ID", "Role", "Baseline"])

        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)

        self.tabs.addTab(self.summary, "Analysis Summary")
        self.tabs.addTab(self.scene_table, "Scenes")
        self.tabs.addTab(self.character_table, "Characters")
        self.tabs.addTab(self.json_preview, "Raw Plan")
        root.addWidget(self.tabs, 2)

        self.import_btn.clicked.connect(self.import_script)
        self.clear_btn.clicked.connect(self.script_text.clear)
        self.analyze_btn.clicked.connect(self.analyze_script)
        self.generate_btn.clicked.connect(self.generate_project)
        self.close_btn.clicked.connect(self.reject)

    def import_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Script",
            str(Path.home()),
            "Scripts (*.md *.txt *.docx *.pdf)"
        )
        if not path:
            return
        try:
            text = read_script_file(path)
            self.script_text.setPlainText(text)
            if not self.project_title.text().strip() or self.project_title.text().strip() == "Historical POV Project":
                self.project_title.setText(Path(path).stem.replace("_", " ").title())
        except Exception as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def analyze_script(self):
        script = self.script_text.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Empty script", "Paste or import a script first.")
            return

        title = self.project_title.text().strip() or "Historical POV Project"

        self.summary.setPlainText(
            "Analyzing script with final generic analyzer...\n\n"
            "This analyzer is story-agnostic and does not contain Cannae-specific rules."
        )
        self.generate_btn.setEnabled(False)

        try:
            context = AnalysisContext(
                project_title=title,
                historical_period=self.period.text().strip(),
                main_pov_character=self.main_pov_character.text().strip(),
                voice_style=self.voice_style.text().strip(),
                target_runtime_minutes=int(self.target_runtime.text().strip() or "75"),
                known_characters=[x.strip() for x in self.known_characters.text().split(",") if x.strip()],
                known_locations=[x.strip() for x in self.known_locations.text().split(",") if x.strip()],
                known_equipment=[x.strip() for x in self.known_equipment.text().split(",") if x.strip()],
            )
            analyzer = GenericScriptAnalyzer()
            plan = analyzer.analyze(script, context)
        except Exception as exc:
            QMessageBox.warning(self, "Analysis failed", str(exc))
            return

        self.plan = plan
        self.populate_preview(plan)
        self.generate_btn.setEnabled(True)

    def populate_preview(self, plan: dict):
        stats = _plan_stats(plan)
        source = plan.get("source", "unknown")
        ollama_error = plan.get("ollama_error", "")

        self.summary.setPlainText(
            f"ANALYSIS COMPLETE\n\n"
            f"Source: {source}\n"
            f"Scenes: {stats['scenes']}\n"
            f"Blocks: {stats['blocks']}\n"
            f"Characters: {stats['characters']}\n"
            f"Locations: {stats['locations']}\n"
            f"Equipment tags: {stats['equipment']}\n"
            f"SFX cues: {stats.get('sfx', 0)}\n"
            f"Ambience cues: {stats.get('ambience', 0)}\n"
            f"Words: {stats['words']}\n"
            f"Estimated runtime: {stats['runtime_minutes']:.1f} min\n"
            f"Estimated voice cost only: ${stats['voice_cost']:.2f}\n"
            f"Images/music/analysis cost: $0.00\n\n"
            f"Next step:\n"
            f"Press Generate Project only if this analysis looks acceptable.\n\n"
            f"Validation:\n{plan.get('validation', {}).get('errors', ['OK'])}"
        )

        scenes = plan.get("scenes") or []
        self.scene_table.setRowCount(len(scenes))
        for r, sc in enumerate(scenes):
            blocks = sc.get("blocks") or []
            words = sum(_words(b.get("text", "")) for b in blocks)
            secs = sum(int(b.get("duration_seconds") or max(8, _words(b.get("text", "")) / 2.15)) for b in blocks)
            values = [
                sc.get("id", ""),
                sc.get("title", ""),
                str(len(blocks)),
                str(words),
                f"{secs/60:.1f} min",
                sc.get("summary", ""),
            ]
            for c, v in enumerate(values):
                self.scene_table.setItem(r, c, QTableWidgetItem(str(v)))

        chars = plan.get("characters") or []
        self.character_table.setRowCount(len(chars))
        for r, ch in enumerate(chars):
            values = [ch.get("id") or ch.get("name") or "", ch.get("role", ""), ch.get("baseline", "")]
            for c, v in enumerate(values):
                self.character_table.setItem(r, c, QTableWidgetItem(str(v)))

        self.json_preview.setPlainText(json.dumps(plan, indent=2, ensure_ascii=False))

    def generate_project(self):
        if not self.plan:
            QMessageBox.warning(self, "No analysis", "Analyze the script first.")
            return

        ok = QMessageBox.question(
            self,
            "Generate Project?",
            "This will replace the currently opened project scenes/blocks with the analyzed production plan.\n\nContinue?"
        ) == QMessageBox.Yes

        if not ok:
            return

        try:
            importer = ScriptImporter(self.db)
            legacy_plan = plan_to_legacy_importer_shape(self.plan)
            result = importer.apply_plan(legacy_plan, replace_existing=True)
            self.generated = True
            QMessageBox.information(
                self,
                "Project Generated",
                f"Created {result['scenes']} scene(s) and {result['blocks']} block(s).\n\n"
                f"Source: {result['source']}"
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Generate failed", str(exc))
