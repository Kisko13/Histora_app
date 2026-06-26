import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QCheckBox, QMessageBox, QComboBox
from hps.providers.image.prompt_builder import build_historical_prompt
from hps.providers.image.openai_image_client import create_openai_image, check_openai_image_config, openai_image_config

class ImageGenerationPanel(QWidget):
    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        self.block_id = None
        self.last_output = ""
        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(self.on_selected_block_changed)
        layout = QVBoxLayout(self)
        title = QLabel("Image Generation / OpenAI Ready")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.block_label = QLabel("Current block: none")
        layout.addWidget(self.block_label)
        row = QHBoxLayout()
        self.provider = QComboBox(); self.provider.addItems(["mock", "openai"])
        self.dry_run = QCheckBox("Dry run / no paid image request"); self.dry_run.setChecked(True)
        self.check_btn = QPushButton("Check OpenAI Config (Free)")
        self.build_prompt_btn = QPushButton("Build Prompt From Block")
        self.generate_btn = QPushButton("Generate Image")
        self.open_btn = QPushButton("Open Last Output")
        for w in [QLabel("Provider"), self.provider, self.dry_run, self.check_btn, self.build_prompt_btn, self.generate_btn, self.open_btn]:
            row.addWidget(w)
        row.addStretch()
        layout.addLayout(row)
        self.cost_label = QLabel("")
        layout.addWidget(self.cost_label)
        layout.addWidget(QLabel("Prompt"))
        self.prompt = QTextEdit(); self.prompt.setMinimumHeight(260)
        layout.addWidget(self.prompt, 2)
        layout.addWidget(QLabel("Log"))
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(180)
        layout.addWidget(self.log, 1)
        self.check_btn.clicked.connect(self.check_config)
        self.build_prompt_btn.clicked.connect(self.build_prompt)
        self.generate_btn.clicked.connect(self.generate)
        self.open_btn.clicked.connect(self.open_last)
        self.provider.currentTextChanged.connect(lambda _: self.refresh_cost())
        self.refresh_cost()

    def on_project_changed(self, db):
        self.db = db

    def on_selected_block_changed(self, block_id):
        self.block_id = block_id or ""
        self.block_label.setText(f"Current block: {self.block_id or 'none'}")

    def set_context(self, db, block_id):
        self.db = db
        self.block_id = block_id
        self.block_label.setText(f"Current block: {block_id or 'none'}")

    def refresh_cost(self):
        if self.provider.currentText() == "mock":
            self.cost_label.setText("Estimated image cost: $0.0000")
        else:
            self.cost_label.setText(f"Estimated image cost: ${openai_image_config()['estimated_cost']:.4f} per image")

    def check_config(self):
        result = check_openai_image_config()
        self.log.append("OPENAI IMAGE CONFIG CHECK")
        self.log.append(str(result))
        if result["ok"]:
            QMessageBox.information(self, "Config OK", "OPENAI_API_KEY is present. No paid request was sent.")
        else:
            QMessageBox.warning(self, "Missing Config", "Missing: " + ", ".join(result["missing"]))

    def build_prompt(self):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        block = self.db.block_with_scene(self.block_id)
        self.prompt.setPlainText(build_historical_prompt(block))
        self.log.append(f"Built image prompt for {self.block_id}")

    def generate(self):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        if not self.prompt.toPlainText().strip():
            self.build_prompt()
        out = self.db.root_dir / "assets" / "images" / f"{self.block_id}_image_test.png"
        if self.provider.currentText() == "mock":
            sidecar = out.with_suffix(".mock_prompt.txt")
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(self.prompt.toPlainText(), encoding="utf-8")
            self.last_output = str(sidecar)
            self.db.execute("UPDATE blocks SET image_status='generated', image_prompt=? WHERE id=?", (self.prompt.toPlainText(), self.block_id))
            QMessageBox.information(self, "Mock Image", f"Saved prompt sidecar:\n{sidecar}")
            return
        if not self.dry_run.isChecked():
            cfg = openai_image_config()
            if QMessageBox.question(self, "Confirm paid image generation", f"This may spend money. Estimated: ${cfg['estimated_cost']:.4f}\nContinue?") != QMessageBox.Yes:
                return
        try:
            result = create_openai_image(self.prompt.toPlainText(), out, dry_run=self.dry_run.isChecked())
            self.log.append(str(result))
            self.last_output = result.get("image_path") or result.get("payload_sidecar") or result.get("response_sidecar") or ""
            self.db.execute("UPDATE blocks SET image_status=?, image_prompt=? WHERE id=?", (result.get("status", "generated"), self.prompt.toPlainText(), self.block_id))
            QMessageBox.information(self, "Image Result", self.last_output)
        except Exception as exc:
            QMessageBox.warning(self, "Image generation failed", str(exc))
            self.log.append("ERROR: " + str(exc))

    def open_last(self):
        if not self.last_output:
            QMessageBox.warning(self, "No output", "No output yet.")
            return
        os.startfile(self.last_output)
