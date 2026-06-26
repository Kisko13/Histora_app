import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QTextEdit, QMessageBox, QFormLayout, QFrame, QScrollArea
)

from hps.core.env_manager import read_env, write_env
from hps.providers.voice.qwen_client import check_config, synthesize_qwen_tts
from hps.core.cost_control import estimate_voice_cost


class ApiSettingsPanel(QWidget):
    def __init__(self, app_root: Path):
        super().__init__()
        self.app_root = Path(app_root)
        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)

        title = QLabel("API Settings / Preflight")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        note = QLabel(
            "Safe at work: Save Settings and Check Config are local/free. "
            "Only Tiny Smoke Test can call Qwen, and it requires paid calls enabled plus confirmation."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        config = self.section("QWEN / DASHSCOPE CONFIG")
        form = QFormLayout()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.workspace = QLineEdit()
        self.region = QComboBox()
        self.region.addItems(["singapore", "beijing"])
        self.default_voice = QLineEdit()

        self.tts_model = QComboBox()
        self.tts_model.addItems(["qwen3-tts-flash", "qwen3-tts-flash-realtime"])
        self.tts_instruct_model = QComboBox()
        self.tts_instruct_model.addItems(["qwen3-tts-instruct-flash", "qwen3-tts-instruct-flash-realtime"])
        self.vd_model = QComboBox()
        self.vd_model.addItems(["qwen3-tts-vd-2026-01-26", "qwen3-tts-vd-realtime-2026-01-15"])
        self.vc_model = QComboBox()
        self.vc_model.addItems(["qwen3-tts-vc-2026-01-22", "qwen3-tts-vc-realtime-2026-01-15"])

        form.addRow("DashScope API Key", self.api_key)
        form.addRow("Workspace ID", self.workspace)
        form.addRow("Region", self.region)
        form.addRow("Default Voice", self.default_voice)
        form.addRow("TTS Model", self.tts_model)
        form.addRow("TTS Instruct Model", self.tts_instruct_model)
        form.addRow("Voice Design Model", self.vd_model)
        form.addRow("Voice Clone Model", self.vc_model)
        config.layout().addLayout(form)
        layout.addWidget(config)

        safety = self.section("SAFETY")
        sf = QFormLayout()
        self.allow_paid = QCheckBox("Allow paid generation")
        self.max_cost = QLineEdit()
        self.cost_per_1k = QLineEdit()
        self.voice_design_cost = QLineEdit()
        sf.addRow("Paid Calls", self.allow_paid)
        sf.addRow("Max Build Cost USD", self.max_cost)
        sf.addRow("Qwen Cost / 1k chars", self.cost_per_1k)
        sf.addRow("Voice Design Cost USD", self.voice_design_cost)
        safety.layout().addLayout(sf)
        layout.addWidget(safety)

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Reload .env")
        self.save_btn = QPushButton("Save .env")
        self.check_btn = QPushButton("Check Config (Free)")
        self.open_env_btn = QPushButton("Open .env")
        buttons.addWidget(self.load_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.check_btn)
        buttons.addWidget(self.open_env_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        smoke = self.section("TINY PAID SMOKE TEST")
        smoke_note = QLabel("Use only at home. Keep text tiny. This creates one WAV if Qwen works.")
        smoke_note.setWordWrap(True)
        smoke.layout().addWidget(smoke_note)
        self.smoke_text = QLineEdit("The flies came first.")
        self.smoke_instructions = QLineEdit("Quiet, controlled, slow, natural.")
        self.smoke_estimate = QLabel("$0.000000")
        self.smoke_btn = QPushButton("Run Tiny Smoke Test")
        smoke.layout().addWidget(QLabel("Tiny text"))
        smoke.layout().addWidget(self.smoke_text)
        smoke.layout().addWidget(QLabel("Instructions"))
        smoke.layout().addWidget(self.smoke_instructions)
        smoke.layout().addWidget(self.smoke_estimate)
        smoke.layout().addWidget(self.smoke_btn)
        layout.addWidget(smoke)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(220)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.output, 1)
        layout.addStretch()

        self.load_btn.clicked.connect(self.load_env)
        self.save_btn.clicked.connect(self.save_env)
        self.check_btn.clicked.connect(self.check_config_free)
        self.open_env_btn.clicked.connect(self.open_env)
        self.smoke_btn.clicked.connect(self.smoke_test)
        self.smoke_text.textChanged.connect(self.update_smoke_estimate)

        self.load_env()

    def section(self, title):
        frame = QFrame()
        frame.setObjectName("Section")
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
        return frame

    def current_values(self):
        return {
            "TTS_PROVIDER": "mock",
            "ALLOW_PAID_GENERATION": "true" if self.allow_paid.isChecked() else "false",
            "MAX_BUILD_COST_USD": self.max_cost.text().strip() or "0.50",
            "ESTIMATED_QWEN_COST_PER_1K_CHARS": self.cost_per_1k.text().strip() or "0.0115",
            "ESTIMATED_QWEN_VOICE_DESIGN_COST_USD": self.voice_design_cost.text().strip() or "0.20",
            "DASHSCOPE_API_KEY": self.api_key.text().strip(),
            "QWEN_WORKSPACE_ID": self.workspace.text().strip(),
            "QWEN_REGION": self.region.currentText(),
            "QWEN_TTS_MODEL": self.tts_model.currentText(),
            "QWEN_TTS_INSTRUCT_MODEL": self.tts_instruct_model.currentText(),
            "QWEN_VOICE_DESIGN_MODEL": "qwen-voice-design",
            "QWEN_VOICE_DESIGN_TARGET_MODEL": self.vd_model.currentText(),
            "QWEN_DEFAULT_VOICE": self.default_voice.text().strip() or "Cherry",
        }

    def load_env(self):
        values = read_env(self.app_root)
        self.api_key.setText(values.get("DASHSCOPE_API_KEY", ""))
        self.workspace.setText(values.get("QWEN_WORKSPACE_ID", ""))
        self.region.setCurrentText(values.get("QWEN_REGION", "singapore"))
        self.default_voice.setText(values.get("QWEN_DEFAULT_VOICE", "Cherry"))
        self.tts_model.setCurrentText(values.get("QWEN_TTS_MODEL", "qwen3-tts-flash"))
        self.tts_instruct_model.setCurrentText(values.get("QWEN_TTS_INSTRUCT_MODEL", "qwen3-tts-instruct-flash"))
        self.vd_model.setCurrentText(values.get("QWEN_VOICE_DESIGN_TARGET_MODEL", "qwen3-tts-vd-2026-01-26"))
        self.allow_paid.setChecked(values.get("ALLOW_PAID_GENERATION", "false").lower() == "true")
        self.max_cost.setText(values.get("MAX_BUILD_COST_USD", "0.50"))
        self.cost_per_1k.setText(values.get("ESTIMATED_QWEN_COST_PER_1K_CHARS", "0.0115"))
        self.voice_design_cost.setText(values.get("ESTIMATED_QWEN_VOICE_DESIGN_COST_USD", "0.20"))
        self.update_smoke_estimate()
        self.output.append("Loaded .env settings.")

    def save_env(self):
        path = write_env(self.app_root, self.current_values())
        QMessageBox.information(self, "Saved", f"Saved settings to:\n{path}\n\nRestart app after changing API settings.")
        self.output.append(f"Saved .env: {path}")

    def check_config_free(self):
        self.save_env()
        result = check_config()
        self.output.append("FREE CONFIG CHECK")
        self.output.append(str(result))
        if result["ok"]:
            QMessageBox.information(self, "Config OK", "Required config values are present. No paid request was sent.")
        else:
            QMessageBox.warning(self, "Missing Config", "Missing: " + ", ".join(result["missing"]))

    def open_env(self):
        path = self.app_root / ".env"
        if not path.exists():
            write_env(self.app_root, self.current_values())
        os.startfile(str(path))

    def update_smoke_estimate(self):
        cost = estimate_voice_cost(len(self.smoke_text.text()), "qwen")
        self.smoke_estimate.setText(f"Estimated smoke-test cost: ${cost:.6f}")

    def smoke_test(self):
        self.save_env()
        if not self.allow_paid.isChecked():
            QMessageBox.warning(self, "Blocked", "Enable 'Allow paid generation' first. Do this only at home.")
            return
        text = self.smoke_text.text().strip()
        if len(text) > 80:
            QMessageBox.warning(self, "Too long", "Keep smoke test under 80 characters.")
            return
        cost = estimate_voice_cost(len(text), "qwen")
        if QMessageBox.question(
            self,
            "Confirm tiny paid smoke test",
            f"This will call Qwen once.\nText length: {len(text)} chars\nEstimated cost: ${cost:.6f}\n\nContinue?"
        ) != QMessageBox.Yes:
            return
        out = self.app_root / "projects" / "cannae_001" / "assets" / "audio_raw" / "smoke_test_qwen.wav"
        try:
            result = synthesize_qwen_tts(
                text=text,
                voice=self.default_voice.text().strip() or "Cherry",
                output_path=out,
                instructions=self.smoke_instructions.text().strip(),
                dry_run=False,
            )
            self.output.append("SMOKE TEST RESULT")
            self.output.append(str(result))
            if result.get("audio_path"):
                QMessageBox.information(self, "Smoke Test OK", f"Audio saved:\n{result['audio_path']}")
                os.startfile(result["audio_path"])
            else:
                QMessageBox.warning(self, "Needs Inspection", f"No audio extracted. Check sidecar:\n{result.get('response_sidecar')}")
        except Exception as exc:
            QMessageBox.warning(self, "Smoke Test Failed", str(exc))
            self.output.append("ERROR: " + str(exc))
