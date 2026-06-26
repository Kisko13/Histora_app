import os
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QLineEdit, QPushButton, QCheckBox, QMessageBox, QComboBox

from hps.providers.voice.qwen_client import check_config, synthesize_qwen_tts, qwen_config
from hps.core.cost_control import paid_generation_allowed, estimate_voice_cost

class OneBlockQwenTest(QWidget):
    def __init__(self):
        super().__init__()
        self.db = None
        self.block_id = None

        layout = QVBoxLayout(self)
        title = QLabel("One-Block Qwen Test Engine")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.status = QLabel("Goal: prove one block can become one Qwen audio file. Dry-run is on by default.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        self.block_label = QLabel("Current block: none")
        self.check_btn = QPushButton("Check Qwen Config")
        self.load_btn = QPushButton("Load Current Block")
        self.dry_run = QCheckBox("Dry run / no paid request")
        self.dry_run.setChecked(True)
        row.addWidget(self.block_label)
        row.addWidget(self.check_btn)
        row.addWidget(self.load_btn)
        row.addWidget(self.dry_run)
        row.addStretch()
        layout.addLayout(row)

        self.voice = QLineEdit("Cherry")
        self.instructions = QTextEdit()
        self.text = QTextEdit()
        layout.addWidget(QLabel("Voice ID / Built-in Voice"))
        layout.addWidget(self.voice)
        layout.addWidget(QLabel("Delivery Instructions"))
        layout.addWidget(self.instructions, 1)
        layout.addWidget(QLabel("Text to Generate"))
        layout.addWidget(self.text, 2)

        action = QHBoxLayout()
        self.estimate_btn = QPushButton("Estimate Cost")
        self.generate_btn = QPushButton("Generate One Block")
        self.open_output_btn = QPushButton("Open Last Output")
        action.addWidget(self.estimate_btn)
        action.addWidget(self.generate_btn)
        action.addWidget(self.open_output_btn)
        action.addStretch()
        layout.addLayout(action)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 2)

        self.last_output_path = ""

        self.check_btn.clicked.connect(self.check_api)
        self.load_btn.clicked.connect(self.load_current_block)
        self.estimate_btn.clicked.connect(self.estimate)
        self.generate_btn.clicked.connect(self.generate)
        self.open_output_btn.clicked.connect(self.open_output)

    def set_context(self, db, block_id):
        self.db = db
        self.block_id = block_id
        self.block_label.setText(f"Current block: {block_id or 'none'}")

    def check_api(self):
        result = check_config()
        self.output.append("CONFIG CHECK")
        self.output.append(str(result))
        if result["ok"]:
            QMessageBox.information(self, "Qwen Config", "Qwen config looks present.")
        else:
            QMessageBox.warning(self, "Qwen Config", "Missing: " + ", ".join(result["missing"]))

    def load_current_block(self):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        block = self.db.block(self.block_id)
        voice_state = self.db.one("SELECT * FROM voice_states WHERE id=?", (block["voice_state_id"],))
        cfg = qwen_config()
        self.voice.setText(cfg["default_voice"])
        self.instructions.setPlainText(voice_state["delivery_prompt"] if voice_state else "")
        self.text.setPlainText(block["text"] or "")
        self.output.append(f"Loaded block {self.block_id}")

    def estimate(self):
        text = self.text.toPlainText()
        est = estimate_voice_cost(len(text), "qwen")
        self.output.append(f"Estimate: {len(text)} chars → ${est:.4f}")

    def _confirm_paid(self, estimated):
        if self.dry_run.isChecked():
            return True
        if not paid_generation_allowed():
            QMessageBox.warning(self, "Paid generation blocked", "Set ALLOW_PAID_GENERATION=true in .env before real Qwen calls.")
            return False
        return QMessageBox.question(
            self,
            "Confirm paid Qwen request",
            f"This may spend money. Estimated: ${estimated:.4f}. Continue?"
        ) == QMessageBox.Yes

    def generate(self):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        text = self.text.toPlainText()
        est = estimate_voice_cost(len(text), "qwen")
        if not self._confirm_paid(est):
            return

        block = self.db.block(self.block_id)
        version = (self.db.scalar("SELECT MAX(version) FROM audio_versions WHERE block_id=?", (self.block_id,)) or 0) + 1
        out = self.db.root_dir / "assets" / "audio_raw" / f"{self.block_id}_qwen_test_v{version:03d}.wav"

        try:
            result = synthesize_qwen_tts(
                text=text,
                voice=self.voice.text(),
                output_path=out,
                instructions=self.instructions.toPlainText(),
                dry_run=self.dry_run.isChecked(),
            )
            self.output.append("\nONE BLOCK RESULT")
            self.output.append(str(result))

            if result.get("audio_path"):
                rel = str(Path(result["audio_path"]).relative_to(self.db.root_dir)).replace("\\", "/")
                self.last_output_path = str(self.db.root_dir / rel)
                status = "generated"
            elif result.get("payload_sidecar"):
                rel = str(Path(result["payload_sidecar"]).relative_to(self.db.root_dir)).replace("\\", "/")
                self.last_output_path = str(self.db.root_dir / rel)
                status = "dry_run"
            else:
                rel = str(Path(result.get("response_sidecar", out.with_suffix(".response.json"))).relative_to(self.db.root_dir)).replace("\\", "/")
                self.last_output_path = str(self.db.root_dir / rel)
                status = "needs_inspection"

            self.db.execute(
                "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (block["project_id"], self.block_id, version, "qwen-test", rel, status, len(text), 0 if self.dry_run.isChecked() else est)
            )
            if status in ("generated", "dry_run", "needs_inspection"):
                self.db.execute("UPDATE blocks SET status='generated' WHERE id=?", (self.block_id,))
            QMessageBox.information(self, "One block test", f"Saved result as version {version}.")
        except Exception as e:
            QMessageBox.warning(self, "One block generation failed", str(e))
            self.output.append("ERROR: " + str(e))

    def open_output(self):
        if not self.last_output_path:
            QMessageBox.warning(self, "No output", "No output yet.")
            return
        os.startfile(self.last_output_path)
