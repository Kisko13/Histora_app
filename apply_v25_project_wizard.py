from pathlib import Path

ROOT = Path(__file__).resolve().parent

wizard_path = ROOT / "hps_qt" / "dialogs" / "project_wizard.py"
wizard_path.parent.mkdir(parents=True, exist_ok=True)

wizard_code = r'''
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
    scenes = plan.get("scenes") or []
    blocks = []
    locations = set()
    equipment = set()
    chars = plan.get("characters") or []

    for sc in scenes:
        for b in sc.get("blocks") or []:
            blocks.append(b)
            for x in b.get("locations") or []:
                locations.add(str(x))
            for x in b.get("equipment") or []:
                equipment.add(str(x))

    total_words = sum(_words(b.get("text", "")) for b in blocks)
    total_chars = sum(len(b.get("text", "")) for b in blocks)
    runtime_seconds = sum(int(b.get("duration_seconds") or max(8, _words(b.get("text", "")) / 2.15)) for b in blocks)

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(chars),
        "locations": len(locations),
        "equipment": len(equipment),
        "words": total_words,
        "runtime_minutes": runtime_seconds / 60,
        "voice_cost": total_chars * 0.000015,
    }


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

        self.ollama_model = QLineEdit("qwen2.5:7b")
        self.ollama_host = QLineEdit("http://127.0.0.1:11434")
        self.use_ollama = QCheckBox("Use local Ollama/Qwen if available")
        self.use_ollama.setChecked(True)

        form.addRow("Project title", self.project_title)
        form.addRow("Historical period", self.period)
        form.addRow("Target runtime minutes", self.target_runtime)
        form.addRow("Voice style", self.voice_style)
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

        self.summary.setPlainText("Analyzing script locally...\n\nThis may take a bit if Ollama/Qwen is running.")
        self.generate_btn.setEnabled(False)

        title = self.project_title.text().strip() or "Historical POV Project"

        try:
            importer = ScriptImporter(self.db)
            plan = importer.build_plan(
                script,
                title,
                use_qwen=self.use_ollama.isChecked(),
                model=self.ollama_model.text().strip(),
                host=self.ollama_host.text().strip(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Analysis failed", str(exc))
            return

        plan.setdefault("title", title)
        plan.setdefault("production_meta", {})
        plan["production_meta"].update({
            "historical_period": self.period.text().strip(),
            "target_runtime_minutes": self.target_runtime.text().strip(),
            "voice_style": self.voice_style.text().strip(),
            "cost_policy": "Only voice generation may use paid/API providers. Script analysis is local/free.",
        })

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
            f"Words: {stats['words']}\n"
            f"Estimated runtime: {stats['runtime_minutes']:.1f} min\n"
            f"Estimated voice cost only: ${stats['voice_cost']:.2f}\n"
            f"Images/music/analysis cost: $0.00\n\n"
            f"Next step:\n"
            f"Press Generate Project only if this analysis looks acceptable.\n\n"
            f"Ollama note:\n{ollama_error if ollama_error else 'No error.'}"
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
            result = importer.apply_plan(self.plan, replace_existing=True)
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
'''

wizard_path.write_text(wizard_code, encoding="utf-8")

studio = ROOT / "studio_qt.py"
text = studio.read_text(encoding="utf-8")

old_import = "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel ROOT="
new_import = "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel from hps_qt.dialogs.project_wizard import ProjectWizardDialog ROOT="
if old_import in text and "ProjectWizardDialog" not in text:
    text = text.replace(old_import, new_import)

old_toolbar = '("Open",self.open_project_dialog),("Paste Script / Local AI Split",self.open_local_ai_split)'
new_toolbar = '("Open",self.open_project_dialog),("New Project Wizard",self.open_project_wizard),("Paste Script / Local AI Split",self.open_local_ai_split)'
if old_toolbar in text and "New Project Wizard" not in text:
    text = text.replace(old_toolbar, new_toolbar)

method_marker = " def open_project_dialog(self):"
method_code = r'''
    def open_project_wizard(self):
        if not self.db:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Create New Historical POV Project",
                str(ROOT / "projects" / "new_project.hps"),
                "Historical POV Project (*.hps)"
            )
            if not path:
                return
            self.open_project(Path(path))

        dlg = ProjectWizardDialog(self.db, self)
        if dlg.exec() and getattr(dlg, "generated", False):
            self.project_label.setText(str(self.db.path))
            p = self.db.project()
            self.title_label.setText(p["title"] if p else "Historical POV Studio")
            self.refresh_all()
            self.auto_select_first_block()
'''
if method_marker in text and "def open_project_wizard" not in text:
    text = text.replace(method_marker, "\n" + method_code + method_marker)

studio.write_text(text, encoding="utf-8")

doc = ROOT / "docs" / "V25_SCRIPT_ANALYSIS_WIZARD.md"
doc.write_text(
    """# V25 Script Analysis Wizard

Adds a safer project creation workflow:

1. New Project Wizard
2. Import `.md`, `.txt`, `.docx`, `.pdf`
3. Paste full script
4. Analyze locally with Ollama/Qwen when available
5. Deterministic fallback when Ollama is unavailable
6. Preview scenes, characters, runtime and voice-only cost
7. Generate project only after review

Cost rule:
- Script analysis: local/free
- Images/music: local/free placeholders/imported assets
- Voice: only paid/API step
""",
    encoding="utf-8",
)

print("V25 Project Wizard applied.")
print("Files changed:")
print(" - hps_qt/dialogs/project_wizard.py")
print(" - studio_qt.py")
print(" - docs/V25_SCRIPT_ANALYSIS_WIZARD.md")