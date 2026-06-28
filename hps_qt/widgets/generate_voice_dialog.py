import re
import json
from pathlib import Path

def clean_voice_text_v26(text: str) -> str:
    """
    Speaker tags are metadata only.
    Never send [Marcus], [Titus], etc. to voice generation.
    """
    text = text or ""
    text = re.sub(r"(?m)^\s*\[[A-Za-z0-9 _.'-]+(?:\|[^\]]+)?\]\s*$", "", text)
    text = text.replace("ENDOFSCRIPT", "")
    text = re.sub(r"(?m)^echo\s+[\"']?Done[\"']?\s*$", "", text, flags=re.I)
    return text.strip()

def assert_voice_text_safe_v26(text: str):
    if re.search(r"(?m)^\s*\[[A-Za-z0-9 _.'-]+(?:\|[^\]]+)?\]\s*$", text or ""):
        raise RuntimeError("Voice text still contains speaker tags. Refusing to generate paid voice.")

def save_voice_request_v26(output_audio_path, block_id, character, provider, voice_text):
    try:
        p = Path(output_audio_path)
        data = {
            "block_id": block_id,
            "character": character,
            "provider": provider,
            "voice_text": voice_text,
            "paid_step": True,
            "speaker_tags_removed": True,
        }
        (p.parent / f"{p.stem}_voice_request.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QLineEdit,
    QPushButton, QCheckBox, QComboBox, QMessageBox, QFormLayout
)

from hps.core.cost_control import paid_generation_allowed, estimate_voice_cost
from hps.providers.voice.qwen_client import synthesize_qwen_tts, qwen_config


class GenerateVoiceDialog(QDialog):
    def __init__(self, parent, db, block_id, default_provider="mock"):
        super().__init__(parent)
        self.db = db
        self.block_id = block_id
        self.result_path = ""
        self.result_status = ""
        self.setWindowTitle("Generate Voice")
        self.resize(760, 760)

        self.block = db.block_with_scene(block_id)
        self.voice_state = db.one("SELECT * FROM voice_states WHERE id=?", (self.block["voice_state_id"],))
        self.character = db.one("SELECT * FROM characters WHERE id=?", (self.block["character_id"],))
        self.voice_row = None
        if self.character and self.character["actor_voice_id"]:
            self.voice_row = db.one("SELECT * FROM voices WHERE id=?", (self.character["actor_voice_id"],))

        layout = QVBoxLayout(self)

        header = QLabel(f"Generate Voice — {self.block['id']} / {self.block['character_id']}")
        header.setObjectName("PanelTitle")
        layout.addWidget(header)

        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["mock", "qwen"])
        self.provider.setCurrentText(default_provider or "mock")

        self.voice_id = QLineEdit(self._default_voice_id())
        self.dry_run = QCheckBox("Dry run / no paid Qwen request")
        self.dry_run.setChecked(True)

        self.cost_label = QLabel("")
        self.char_label = QLabel("")
        self.status_label = QLabel("")

        form.addRow("Scene", QLabel(self.block["scene_title"]))
        form.addRow("Character", QLabel(self.block["character_id"]))
        form.addRow("Voice Profile", QLabel(self.voice_row["display_name"] if self.voice_row else "-"))
        form.addRow("Provider", self.provider)
        form.addRow("Voice ID / built-in voice", self.voice_id)
        form.addRow("Safety", self.dry_run)
        form.addRow("Characters", self.char_label)
        form.addRow("Estimated Cost", self.cost_label)
        form.addRow("Status", self.status_label)
        layout.addLayout(form)

        layout.addWidget(QLabel("Delivery Instructions"))
        self.instructions = QTextEdit()
        self.instructions.setPlainText(self.voice_state["delivery_prompt"] if self.voice_state else "")
        layout.addWidget(self.instructions, 1)

        layout.addWidget(QLabel("Text"))
        self.text = QTextEdit()
        self.text.setPlainText(self.block["text"] or "")
        layout.addWidget(self.text, 2)

        row = QHBoxLayout()
        self.estimate_btn = QPushButton("Refresh Estimate")
        self.generate_btn = QPushButton("Generate")
        self.cancel_btn = QPushButton("Cancel")
        row.addWidget(self.estimate_btn)
        row.addStretch()
        row.addWidget(self.generate_btn)
        row.addWidget(self.cancel_btn)
        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        self.estimate_btn.clicked.connect(self.refresh_estimate)
        self.provider.currentTextChanged.connect(lambda _: self.refresh_estimate())
        self.text.textChanged.connect(self.refresh_estimate)
        self.dry_run.stateChanged.connect(lambda _: self.refresh_estimate())
        self.generate_btn.clicked.connect(self.generate)
        self.cancel_btn.clicked.connect(self.reject)

        self.refresh_estimate()

    def _default_voice_id(self):
        if self.voice_row and self.voice_row["provider_voice_id"]:
            return self.voice_row["provider_voice_id"]
        return qwen_config()["default_voice"]

    def refresh_estimate(self):
        text = self.text.toPlainText()
        provider = self.provider.currentText()
        chars = len(text)
        cost = estimate_voice_cost(chars, provider)
        self.char_label.setText(str(chars))
        self.cost_label.setText(f"${cost:.4f}")
        if provider == "mock":
            self.status_label.setText("Free mock generation")
        elif self.dry_run.isChecked():
            self.status_label.setText("Qwen dry-run, no paid request")
        elif not paid_generation_allowed():
            self.status_label.setText("Blocked: ALLOW_PAID_GENERATION=false")
        else:
            self.status_label.setText("Paid Qwen request allowed")

    def _confirm_paid_if_needed(self):
        provider = self.provider.currentText()
        if provider == "mock" or self.dry_run.isChecked():
            return True
        if not paid_generation_allowed():
            QMessageBox.warning(self, "Paid generation blocked", "Set ALLOW_PAID_GENERATION=true in .env before real Qwen calls.")
            return False
        cost = estimate_voice_cost(len(self.text.toPlainText()), "qwen")
        return QMessageBox.question(self, "Confirm paid Qwen request", f"This may spend money. Estimated: ${cost:.4f}. Continue?") == QMessageBox.Yes

    def generate(self):
        if not self._confirm_paid_if_needed():
            return

        provider = self.provider.currentText()
        version = (self.db.scalar("SELECT MAX(version) FROM audio_versions WHERE block_id=?", (self.block_id,)) or 0) + 1
        char_count = len(self.text.toPlainText())
        project_id = self.block["project_id"]
        out_dir = self.db.root_dir / "assets" / "audio_raw"
        out_dir.mkdir(parents=True, exist_ok=True)

        if provider == "mock":
            out = out_dir / f"{self.block_id}_mock_v{version:03d}.txt"
            out.write_text(
                "MOCK AUDIO — FREE\\n\\n"
                f"BLOCK: {self.block_id}\\n"
                f"CHARACTER: {self.block['character_id']}\\n"
                f"VOICE: {self.voice_id.text()}\\n\\n"
                f"DELIVERY:\\n{self.instructions.toPlainText()}\\n\\n"
                f"SCRIPT:\\n{self.text.toPlainText()}\\n",
                encoding="utf-8"
            )
            rel = str(out.relative_to(self.db.root_dir)).replace("\\\\", "/")
            self.db.execute(
                "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, self.block_id, version, "mock-dialog", rel, "generated", char_count, 0.0)
            )
            self.db.execute("UPDATE blocks SET status='generated', issue='' WHERE id=?", (self.block_id,))
            self.result_path = str(out)
            self.result_status = "generated"
            QMessageBox.information(self, "Generated", f"Saved mock version {version}.")
            self.accept()
            return

        out = out_dir / f"{self.block_id}_qwen_v{version:03d}.wav"
        try:
            result = synthesize_qwen_tts(
                text=self.text.toPlainText(),
                voice=self.voice_id.text(),
                output_path=out,
                instructions=self.instructions.toPlainText(),
                dry_run=self.dry_run.isChecked(),
            )
            self.output.append(str(result))
            est = 0.0 if self.dry_run.isChecked() else estimate_voice_cost(char_count, "qwen")

            if result.get("audio_path"):
                final_path = Path(result["audio_path"])
                rel = str(final_path.relative_to(self.db.root_dir)).replace("\\\\", "/")
                status = "generated"
                block_status = "generated"
                issue = ""
            elif result.get("payload_sidecar"):
                final_path = Path(result["payload_sidecar"])
                rel = str(final_path.relative_to(self.db.root_dir)).replace("\\\\", "/")
                status = "dry_run"
                block_status = self.block["status"]
                issue = "Dry-run payload created; no Qwen call made"
            else:
                final_path = Path(result.get("response_sidecar", out.with_suffix(".response.json")))
                rel = str(final_path.relative_to(self.db.root_dir)).replace("\\\\", "/")
                status = result.get("status", "needs_inspection")
                block_status = "needs_inspection"
                issue = "Inspect Qwen response sidecar"

            self.db.execute(
                "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, self.block_id, version, "qwen-dialog", rel, status, char_count, est)
            )
            self.db.execute("UPDATE blocks SET status=?, issue=? WHERE id=?", (block_status, issue, self.block_id))
            self.result_path = str(final_path)
            self.result_status = status
            QMessageBox.information(self, "Generated", f"Saved result as version {version}.")
            self.accept()

        except Exception as exc:
            QMessageBox.warning(self, "Generation failed", str(exc))
            self.output.append("ERROR: " + str(exc))
