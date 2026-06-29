from pathlib import Path

ROOT = Path(__file__).resolve().parent
studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

# Add import
if "from hps.core.batch_production import run_batch_production" not in s:
    s = s.replace(
        "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel",
        "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel "
        "from hps.core.batch_production import run_batch_production"
    )

# Add toolbar button into existing toolbar list
s = s.replace(
    '("Generate Voice",self.open_generate_voice_dialog),("Build",self.build_episode)',
    '("Generate Voice",self.open_generate_voice_dialog),("Generate Missing Assets",self.v27_generate_missing_assets),("Build",self.build_episode)'
)

# Add method before build_episode
if "def v27_generate_missing_assets(self):" not in s:
    s = s.replace(
        "def build_episode(self):",
        '''def v27_generate_missing_assets(self):
        if not self.db:
            return
        limit, ok = QInputDialog.getInt(
            self,
            "Batch Production",
            "How many missing blocks per asset type? 0 = ALL",
            5,
            0,
            100000,
            1
        )
        if not ok:
            return
        provider = self.provider_box.currentText()
        try:
            report = run_batch_production(
                self.db,
                provider=provider,
                generate_voice=True,
                generate_images=True,
                generate_music=True,
                limit=None if limit == 0 else limit,
            )
            lines = [f"{step['step']}: {step['generated']}" for step in report["steps"]]
            QMessageBox.information(
                self,
                "Batch Production Complete",
                "Generated:\\n" + "\\n".join(lines) + f"\\n\\nReport:\\n{report['report_path']}"
            )
            self.refresh_production_ui()
        except Exception as e:
            QMessageBox.critical(self, "Batch Production Failed", str(e))

    def build_episode(self):'''
    )

studio.write_text(s, encoding="utf-8")
print("Generate Missing Assets button added.")