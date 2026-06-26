from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, QDialog,
    QLineEdit, QFormLayout, QDialogButtonBox, QSpinBox
)

from hps.controllers.production_orchestrator import ProductionOrchestrator
from hps.core.production_director import ProductionDirector
from hps.core.local_assets import write_budget_forecast, write_recovery_snapshot
from hps.core.script_importer import ScriptImporter
from hps.local_ai.ollama_client import OllamaClient
from hps.core.asset_library import load_style_bible, save_style_bible


class ScriptImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local AI Script Splitter — Qwen/Ollama")
        self.resize(900, 720)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Paste the full script. This uses LOCAL Ollama/Qwen if available. "
            "If Ollama is not running, it falls back to deterministic free splitting. "
            "No paid API is used here."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.title = QLineEdit("Historical POV Project")
        self.model = QLineEdit("qwen2.5:7b")
        self.host = QLineEdit("http://127.0.0.1:11434")
        self.use_qwen = QCheckBox("Use local Qwen/Ollama if available")
        self.use_qwen.setChecked(True)
        form.addRow("Project title", self.title)
        form.addRow("Ollama model", self.model)
        form.addRow("Ollama host", self.host)
        form.addRow("Local AI", self.use_qwen)
        layout.addLayout(form)
        self.script = QTextEdit()
        self.script.setPlaceholderText("Paste 30–90 minute narration script here...")
        layout.addWidget(self.script, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Split Script + Replace Project")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class StyleBibleDialog(QDialog):
    def __init__(self, current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local Style Bible")
        self.resize(820, 520)
        current = current or {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Saved once, injected into every image prompt. Local/free."))
        form = QFormLayout()
        self.visual = QTextEdit(current.get("visual_style", "cinematic historical realism, immersive first-person POV, grounded details"))
        self.camera = QTextEdit(current.get("camera", "35mm documentary still, eye-level POV, natural composition"))
        self.lighting = QTextEdit(current.get("lighting", "natural practical light, smoke/dust/haze where appropriate"))
        self.negative = QTextEdit(current.get("negative_prompt", "fantasy armor, anachronistic weapons, modern objects, text, watermark"))
        for w in [self.visual, self.camera, self.lighting, self.negative]:
            w.setMaximumHeight(80)
        form.addRow("Visual style", self.visual)
        form.addRow("Camera", self.camera)
        form.addRow("Lighting", self.lighting)
        form.addRow("Negative prompt", self.negative)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def value(self):
        return {
            "visual_style": self.visual.toPlainText().strip(),
            "camera": self.camera.toPlainText().strip(),
            "lighting": self.lighting.toPlainText().strip(),
            "negative_prompt": self.negative.toPlainText().strip(),
        }


class V24OrchestratorPanel(QWidget):
    """Production Orchestrator UI: full-pipeline brain, free-first by default."""

    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.db = None
        self.progress_callback = None
        self.changed_callback = None
        self.provider_getter = lambda: "mock"

        layout = QVBoxLayout(self)
        title = QLabel("V24 Production Orchestrator — Local AI / Voice-Only Cost Pipeline")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        policy = QLabel(
            "Hard policy: script split, director, images, music, reports, orchestration and assembly are LOCAL/FREE. "
            "Only voice generation may use a paid/API provider, and the .env budget guard still blocks it unless enabled."
        )
        policy.setWordWrap(True)
        policy.setStyleSheet("padding:8px;background:#242424;border:1px solid #444;")
        layout.addWidget(policy)

        local_row = QHBoxLayout()
        self.split_btn = QPushButton("Paste Full Script → Local AI Split")
        self.ollama_check_btn = QPushButton("Check Ollama/Qwen")
        self.style_btn = QPushButton("Edit Style Bible")
        self.asset_btn = QPushButton("Export Asset Library")
        local_row.addWidget(self.split_btn)
        local_row.addWidget(self.ollama_check_btn)
        local_row.addWidget(self.style_btn)
        local_row.addWidget(self.asset_btn)
        local_row.addStretch()
        layout.addLayout(local_row)

        opts = QHBoxLayout()
        self.run_voice = QCheckBox("Also run voice generation")
        self.run_voice.setChecked(False)
        self.offline_assets = QCheckBox("Create local image/music placeholders")
        self.offline_assets.setChecked(True)
        self.build_assembly = QCheckBox("Build assembly outputs")
        self.build_assembly.setChecked(True)
        opts.addWidget(self.run_voice)
        opts.addWidget(self.offline_assets)
        opts.addWidget(self.build_assembly)
        opts.addStretch()
        layout.addLayout(opts)

        row = QHBoxLayout()
        self.plan_btn = QPushButton("Rebuild Plan")
        self.run_btn = QPushButton("Run V24 Pipeline")
        self.director_btn = QPushButton("Export Director Report")
        self.recovery_btn = QPushButton("Write Recovery Snapshot")
        self.budget_btn = QPushButton("Export Budget Forecast")
        row.addWidget(self.plan_btn)
        row.addWidget(self.run_btn)
        row.addWidget(self.director_btn)
        row.addWidget(self.recovery_btn)
        row.addWidget(self.budget_btn)
        row.addStretch()
        layout.addLayout(row)

        self.summary = QLabel("No project loaded.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Task", "Block", "Status", "Dependency", "Attempts", "Cost", "Message"])
        layout.addWidget(self.table, 2)

        layout.addWidget(QLabel("Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        layout.addWidget(self.log, 1)

        self.plan_btn.clicked.connect(self.rebuild_plan)
        self.run_btn.clicked.connect(self.run_pipeline)
        self.director_btn.clicked.connect(self.export_director)
        self.recovery_btn.clicked.connect(self.write_recovery)
        self.budget_btn.clicked.connect(self.write_budget)
        self.split_btn.clicked.connect(self.import_script)
        self.ollama_check_btn.clicked.connect(self.check_ollama)
        self.style_btn.clicked.connect(self.edit_style_bible)
        self.asset_btn.clicked.connect(self.export_assets)

        if hasattr(app_state, "project_changed"):
            app_state.project_changed.connect(self.set_context)

    def set_context(self, db=None, *_):
        self.db = db or getattr(self.state, "db", None)
        self.refresh()

    def set_callbacks(self, progress_callback=None, changed_callback=None, provider_getter=None):
        self.progress_callback = progress_callback
        self.changed_callback = changed_callback
        if provider_getter:
            self.provider_getter = provider_getter

    def _provider(self):
        try:
            return self.provider_getter()
        except Exception:
            return "mock"

    def refresh(self):
        if not self.db:
            self.summary.setText("No project loaded.")
            self.table.setRowCount(0)
            return
        jobs = self.db.production_jobs()
        counts = {}
        for j in jobs:
            counts[j["status"]] = counts.get(j["status"], 0) + 1
        sp = self.db.story_progress(); vp = self.db.voice_progress(); ip = self.db.image_progress(); mp = self.db.music_progress(); ap = self.db.assembly_progress()
        self.summary.setText(
            f"Project: {self.db.project()['title'] if self.db.project() else 'Untitled'} | "
            f"Story {sp[0]}/{sp[1]} | Voice {vp[0]}/{vp[1]} | Images {ip[0]}/{ip[1]} | "
            f"Music {mp[0]}/{mp[1]} | Assembly {ap[0]}/{ap[1]} | Jobs: " +
            (", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) if counts else "no plan yet")
        )
        self.table.setRowCount(len(jobs))
        for i, j in enumerate(jobs):
            vals = [j["id"], j["task_type"], j["block_id"], j["status"], j["dependency_key"], j["attempt_count"], f"${j['estimated_cost_usd']:.4f}", j["message"]]
            for c, v in enumerate(vals):
                self.table.setItem(i, c, QTableWidgetItem(str(v)))

    def import_script(self):
        if not self.db:
            QMessageBox.warning(self, "No project", "Open or create a project first.")
            return
        dlg = ScriptImportDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        script = dlg.script.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Empty script", "Paste a script first.")
            return
        ok = QMessageBox.question(
            self, "Replace project blocks?",
            "This will replace existing scenes/blocks in the opened project with the new local production split. Continue?"
        ) == QMessageBox.Yes
        if not ok:
            return
        self.log.append("Splitting script locally...")
        importer = ScriptImporter(self.db)
        plan = importer.build_plan(script, dlg.title.text().strip(), use_qwen=dlg.use_qwen.isChecked(), model=dlg.model.text().strip(), host=dlg.host.text().strip())
        result = importer.apply_plan(plan, replace_existing=True)
        self.log.append(f"Script imported: {result['scenes']} scene(s), {result['blocks']} block(s), source={result['source']}")
        if plan.get("ollama_error"):
            self.log.append("Ollama note: " + str(plan.get("ollama_error"))[:500])
        self.rebuild_plan()
        if self.changed_callback:
            self.changed_callback()
        QMessageBox.information(self, "Script Split Complete", f"Created {result['scenes']} scenes and {result['blocks']} blocks.\nSource: {result['source']}")

    def check_ollama(self):
        client = OllamaClient()
        if client.is_available():
            QMessageBox.information(self, "Ollama", "Ollama is reachable on localhost. Local Qwen splitting can run for free.")
        else:
            QMessageBox.warning(self, "Ollama", "Ollama is not reachable. The app will still use deterministic free splitting.")

    def edit_style_bible(self):
        if not self.db:
            return
        dlg = StyleBibleDialog(load_style_bible(self.db), self)
        if dlg.exec() == QDialog.Accepted:
            path = save_style_bible(self.db, dlg.value())
            self.log.append(f"Style bible saved: {path}")

    def export_assets(self):
        if not self.db:
            return
        from hps.core.asset_library import register_assets_from_plan
        # asset index is already written by script import; this action ensures folders exist and reports path.
        p = self.db.root_dir / "assets" / "library" / "asset_index.json"
        self.log.append(f"Asset library: {p}")
        QMessageBox.information(self, "Asset Library", str(p))

    def rebuild_plan(self):
        if not self.db:
            return
        provider = self._provider()
        jobs = ProductionOrchestrator(self.db, provider).rebuild_plan()
        self.log.append(f"Rebuilt V24 plan: {len(jobs)} job(s).")
        self.refresh()
        if self.changed_callback:
            self.changed_callback()

    def run_pipeline(self):
        if not self.db:
            return
        provider = self._provider()
        if self.run_voice.isChecked() and provider != "mock":
            ok = QMessageBox.question(
                self,
                "Confirm voice generation",
                "This will run voice generation. That is the only V24 step allowed to spend money, and .env budget guard still applies. Continue?",
            ) == QMessageBox.Yes
            if not ok:
                return
        orch = ProductionOrchestrator(
            self.db,
            voice_provider=provider,
            allow_voice_generation=self.run_voice.isChecked(),
            progress=self.progress_callback,
        )
        result = orch.run_pending(offline_assets=self.offline_assets.isChecked(), build_assembly=self.build_assembly.isChecked())
        for line in result["log"]:
            self.log.append(line)
        self.refresh()
        if self.changed_callback:
            self.changed_callback()

    def export_director(self):
        if not self.db:
            return
        path = ProductionDirector(self.db).export_report()
        self.log.append(f"Director report: {path}")
        QMessageBox.information(self, "Director Report", str(path))

    def write_recovery(self):
        if not self.db:
            return
        path = write_recovery_snapshot(self.db, "manual_snapshot")
        self.log.append(f"Recovery snapshot: {path}")
        QMessageBox.information(self, "Recovery Snapshot", str(path))

    def write_budget(self):
        if not self.db:
            return
        path = write_budget_forecast(self.db, self._provider())
        self.log.append(f"Budget forecast: {path}")
        QMessageBox.information(self, "Budget Forecast", str(path))
