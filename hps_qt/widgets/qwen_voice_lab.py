from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QLineEdit,
    QPushButton, QCheckBox, QMessageBox, QScrollArea, QFrame
)

from hps.providers.voice.qwen_client import check_config, create_voice_design, synthesize_qwen_tts
from hps.core.cost_control import paid_generation_allowed, qwen_voice_design_cost, estimate_voice_cost


class QwenVoiceLab(QWidget):
    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)

        title = QLabel("Qwen Voice Lab")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.status = QLabel(
            "Safe lab for Qwen tests. Config check is free/local. Dry-run is ON by default and sends no paid request."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        connection = self.section("CONNECTION")
        row = QHBoxLayout()
        self.check_btn = QPushButton("Check Config (Free)")
        self.dry_run = QCheckBox("Dry run / no paid requests")
        self.dry_run.setChecked(True)
        row.addWidget(self.check_btn)
        row.addWidget(self.dry_run)
        row.addStretch()
        connection.layout().addLayout(row)
        self.config_result = QTextEdit()
        self.config_result.setReadOnly(True)
        self.config_result.setMinimumHeight(90)
        connection.layout().addWidget(self.config_result)
        layout.addWidget(connection)

        voice_design = self.section("VOICE DESIGN")
        self.preferred_name = QLineEdit("marcus_test_voice")
        self.preview_text = QLineEdit("The flies always found us before dawn.")
        self.voice_prompt = QTextEdit()
        self.voice_prompt.setMinimumHeight(150)
        self.voice_prompt.setPlainText(
            "A restrained middle-aged male narrator with a deep rough soldier voice, calm and tired, "
            "quiet memory tone, not theatrical, suitable for immersive historical documentary narration."
        )
        self.design_btn = QPushButton("Create/Test Voice Design")
        voice_design.layout().addWidget(QLabel("Preferred Voice Name"))
        voice_design.layout().addWidget(self.preferred_name)
        voice_design.layout().addWidget(QLabel("Preview Text"))
        voice_design.layout().addWidget(self.preview_text)
        voice_design.layout().addWidget(QLabel("Voice Design Prompt"))
        voice_design.layout().addWidget(self.voice_prompt)
        voice_design.layout().addWidget(self.design_btn)
        layout.addWidget(voice_design)

        tts = self.section("TEST TTS")
        self.tts_voice = QLineEdit("Cherry")
        self.tts_text = QTextEdit()
        self.tts_text.setMinimumHeight(130)
        self.tts_text.setPlainText("The stone again. Same place. Left hip, just below the bone.")
        self.tts_instructions = QTextEdit()
        self.tts_instructions.setMinimumHeight(110)
        self.tts_instructions.setPlainText(
            "Quiet, intimate, controlled. Slow pace. Long natural pauses. Never theatrical."
        )
        self.tts_btn = QPushButton("Create Test TTS")
        tts.layout().addWidget(QLabel("TTS Voice ID / built-in voice"))
        tts.layout().addWidget(self.tts_voice)
        tts.layout().addWidget(QLabel("Test TTS Text"))
        tts.layout().addWidget(self.tts_text)
        tts.layout().addWidget(QLabel("Delivery Instructions"))
        tts.layout().addWidget(self.tts_instructions)
        tts.layout().addWidget(self.tts_btn)
        layout.addWidget(tts)

        output_section = self.section("LOG")
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(220)
        output_section.layout().addWidget(self.output)
        layout.addWidget(output_section)

        layout.addStretch()

        self.check_btn.clicked.connect(self.check_api)
        self.design_btn.clicked.connect(self.create_design)
        self.tts_btn.clicked.connect(self.create_tts)

    def section(self, title):
        frame = QFrame()
        frame.setObjectName("Section")
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
        return frame

    def check_api(self):
        result = check_config()
        self.config_result.setPlainText(str(result))
        self.output.append("CONFIG CHECK")
        self.output.append(str(result))
        if result["ok"]:
            QMessageBox.information(self, "Qwen Config", "Qwen config values are present. No paid request was sent.")
        else:
            QMessageBox.warning(self, "Qwen Config", "Missing: " + ", ".join(result["missing"]))

    def _confirm_paid(self, estimated):
        if self.dry_run.isChecked():
            return True
        if not paid_generation_allowed():
            QMessageBox.warning(
                self,
                "Paid generation blocked",
                "Set ALLOW_PAID_GENERATION=true in .env before real Qwen calls."
            )
            return False
        return QMessageBox.question(
            self,
            "Confirm paid Qwen request",
            f"This may spend money. Estimated: ${estimated:.4f}. Continue?"
        ) == QMessageBox.Yes

    def create_design(self):
        est = qwen_voice_design_cost()
        if not self._confirm_paid(est):
            return
        try:
            out_dir = Path("projects/cannae_001/assets/audio_raw")
            result = create_voice_design(
                voice_prompt=self.voice_prompt.toPlainText(),
                preferred_name=self.preferred_name.text(),
                preview_text=self.preview_text.text(),
                output_dir=out_dir,
                dry_run=self.dry_run.isChecked(),
            )
            self.output.append("\nVOICE DESIGN RESULT")
            self.output.append(str(result))
        except Exception as e:
            QMessageBox.warning(self, "Voice design failed", str(e))
            self.output.append("ERROR: " + str(e))

    def create_tts(self):
        text = self.tts_text.toPlainText()
        est = estimate_voice_cost(len(text), "qwen")
        if not self._confirm_paid(est):
            return
        try:
            out = Path("projects/cannae_001/assets/audio_raw/qwen_voice_lab_test.wav")
            result = synthesize_qwen_tts(
                text=text,
                voice=self.tts_voice.text(),
                output_path=out,
                instructions=self.tts_instructions.toPlainText(),
                dry_run=self.dry_run.isChecked(),
            )
            self.output.append("\nTTS RESULT")
            self.output.append(str(result))
        except Exception as e:
            QMessageBox.warning(self, "TTS failed", str(e))
            self.output.append("ERROR: " + str(e))
