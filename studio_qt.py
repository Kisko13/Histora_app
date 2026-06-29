from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from hps.controllers.production_controller import ProductionController
from hps.core.batch_production import run_batch_production, plan_v28_media
from hps.core.v29_timeline_engine import build_timeline
from hps.core.v29_assembly_engine import build_v29_episode
from hps.core.v30_assembly_engine import build_v30_episode_package
from hps.core.v30_health import create_v30_health_report
from hps.core.v31_asset_library import normalize_project_assets
from hps.core.v31_timeline_preview import build_v31_timeline_preview
from hps.core.v31_assembly_package import build_v31_production_package
from hps.core.v31_health import create_v31_health_report
from hps.core.v32_renderer import build_v32_render_package, render_v32_test_mp4
from hps.core.v33_renderer import build_v33_render_package, render_v33_test_mp4
from hps.core.v34_full_episode_renderer import build_v34_full_episode_package, render_v34_full_episode
from hps.core.v35_workflow_dashboard import build_v35_dashboard, build_v35_review_queue, latest_episode_path
from hps.core.v36_voice_workflow import build_v36_voiceover_plan, generate_v36_voice_queue, provider_chain_from_env
from hps.core.v37_voice_providers import (
    build_v37_voice_provider_health,
    generate_v37_voice_queue,
    provider_chain_from_env_v37,
    test_v37_voice_provider,
)
from hps.core.cost_control import cost_guard
from hps.core.project_service import ProjectService
from hps.core.voice_pipeline import generate_voice_for_block
from hps.pipeline.build import BuildPipeline
from hps.pipeline.export import export_capcut_csv
from hps_qt.app_state import AppState
from hps_qt.dialogs.project_wizard import ProjectWizardDialog
from hps_qt.dialogs.production_dialog import ProductionDialog
from hps_qt.widgets.api_settings_panel import ApiSettingsPanel
from hps_qt.widgets.assembly_engine_panel import AssemblyEnginePanel
from hps_qt.widgets.assembly_studio_panel import AssemblyStudioPanel
from hps_qt.widgets.assistant_panel import AssistantPanel
from hps_qt.widgets.block_state_panel import BlockStatePanel
from hps_qt.widgets.block_workspace import BlockWorkspace
from hps_qt.widgets.cost_panel import CostPanel
from hps_qt.widgets.generate_voice_dialog import GenerateVoiceDialog
from hps_qt.widgets.image_generation_panel import ImageGenerationPanel
from hps_qt.widgets.image_studio_panel import ImageStudioPanel
from hps_qt.widgets.manager_panels import CharacterManager, ImageManager
from hps_qt.widgets.mission_control import MissionControl
from hps_qt.widgets.mission_dashboard import MissionDashboard
from hps_qt.widgets.music_studio_panel import MusicStudioPanel
from hps_qt.widgets.qwen_voice_lab import QwenVoiceLab
from hps_qt.widgets.queue_panel import QueuePanel
from hps_qt.widgets.scene_explorer import SceneExplorer
from hps_qt.widgets.smart_inspector import SmartInspector
from hps_qt.widgets.stat_card import StatCard
from hps_qt.widgets.timeline_panel import TimelinePanel
from hps_qt.widgets.timeline_preview_panel import TimelinePreviewPanel
from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel
from hps_qt.widgets.workflow_engine_panel import WorkflowEnginePanel
from hps_qt.widgets.workspace_groups import WorkspaceGroups

ROOT = Path(__file__).resolve().parent

STYLE = """
QMainWindow,QWidget{background:#1e1e1e;color:#e8e8e8;font-family:Segoe UI;font-size:10pt}
QLabel{color:#e8e8e8}
QPushButton{background:#3a3a3a;color:#e8e8e8;border:1px solid #555;padding:7px}
QPushButton:hover{background:#4a4a4a}
QComboBox,QLineEdit,QTextEdit,QListWidget{background:#151515;color:#e8e8e8;border:1px solid #444}
QTreeWidget,QTableWidget{background:#151515;color:#e8e8e8;border:1px solid #444}
QTabBar::tab{background:#2d2d30;color:#ddd;padding:8px 12px}
QTabBar::tab:selected{background:#3a3a3a}
QProgressBar{background:#151515;border:1px solid #444;text-align:center}
QProgressBar::chunk{background:#4cc2ff}
#StatCard,#InfoBadge,#Section{background:#252526;border:1px solid #333;border-radius:4px}
#CardTitle,#BadgeTitle{color:#a0a0a0;font-size:9pt;font-weight:bold}
#CardValue{color:#fff;font-size:24pt;font-weight:bold}
#BadgeValue{color:#fff;font-size:13pt;font-weight:bold}
#WorkspaceTitle{font-size:18pt;font-weight:bold}
#PanelTitle{font-size:16pt;font-weight:bold}
#AudioPlaceholder{background:#101010;border:1px solid #444;padding:18px;color:#a0a0a0}
#Overview{color:#ddd;padding:6px}
#SectionTitle{font-weight:bold;color:#4cc2ff}
"""


class StudioQt(QMainWindow):
    """Main desktop shell for Historical POV Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Historical POV Studio v37 — Voice Provider Manager")
        self.resize(1800, 1060)

        self.service = ProjectService()
        self.db = None
        self.selected_block_id = None
        self.state = AppState()
        self.production_controller = None

        self.provider_box = QComboBox()
        self.provider_box.addItems(["qwen", "mock"])
        self.mode_box = QComboBox()
        self.mode_box.addItems(["missing", "redo", "all"])

        self.build_ui()

        default = ROOT / "projects" / "cannae_001" / "cannae_001.hps"
        if default.exists():
            self.open_project(default)

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)
        # V34.1 toolbar cleanup: keep only the current production workflow visible.
        # Older V31/V32/V33 buttons are intentionally removed from the main toolbar
        # so the full episode render controls stay visible on smaller screens.
        for text, fn in [
            ("Open", self.open_project_dialog),
            ("New Wizard", self.open_project_wizard),
            ("Paste Script", self.open_local_ai_split),
            ("Generate Voice", self.open_generate_voice_dialog),
            ("Voice Providers", self.v37_voice_provider_health),
            ("Test Voice", self.v37_test_voice_provider),
            ("Voiceover Plan", self.v36_voiceover_plan),
            ("Generate Voice Queue", self.v37_generate_voice_queue),
            ("Plan Media", self.v28_plan_media),
            ("Asset Library", self.v31_asset_library),
            ("Build Timeline", self.v29_build_timeline),
            ("Preview", self.v31_preview_timeline),
            ("Health", self.v35_dashboard),
            ("Review Queue", self.v35_review_queue),
            ("Generate Assets", self.v27_generate_missing_assets),
            ("V34 Package", self.v34_build_full_package),
            ("Render Episode", self.v34_render_full_episode),
            ("Open Episode", self.v35_open_episode),
            ("Next Task", self.open_next_production_task),
            ("Export", self.export_capcut),
        ]:
            button = QPushButton(text)
            button.clicked.connect(fn)
            toolbar.addWidget(button)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Provider "))
        toolbar.addWidget(self.provider_box)
        toolbar.addWidget(QLabel(" Mode "))
        toolbar.addWidget(self.mode_box)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.title_label = QLabel("Historical POV Studio")
        self.title_label.setStyleSheet("font-size:26pt;font-weight:bold")
        self.project_label = QLabel("No project loaded")
        self.project_label.setStyleSheet("color:#a0a0a0")
        layout.addWidget(self.title_label)
        layout.addWidget(self.project_label)

        self.mission = MissionControl()
        layout.addWidget(self.mission)

        cards = QHBoxLayout()
        self.cards = {}
        for name in ["approved", "generated", "missing", "redo", "rejected", "complete"]:
            card = StatCard(name, "0")
            self.cards[name] = card
            cards.addWidget(card)
        layout.addLayout(cards)

        self.workspace = BlockWorkspace()
        if hasattr(self.workspace, "generate_clicked"):
            self.workspace.generate_clicked.connect(self.open_generate_voice_dialog)
        self.workspace.generate_block_clicked.connect(self.generate_single_block)
        self.workspace.approve_clicked.connect(self.approve_latest)
        self.workspace.redo_clicked.connect(self.mark_redo)
        self.workspace.reject_clicked.connect(self.reject_block)
        self.workspace.open_audio_clicked.connect(self.open_latest_audio)
        self.workspace.open_selected_version_clicked.connect(self.open_selected_version)
        self.workspace.save_clicked.connect(self.save_block)
        self.workspace.image_approve_clicked.connect(lambda: self.set_image_status("approved"))
        self.workspace.image_redo_clicked.connect(lambda: self.set_image_status("redo"))
        self.workspace.music_approve_clicked.connect(lambda: self.set_music_status("approved"))

        self.queue_panel = QueuePanel()
        self.character_manager = CharacterManager()
        self.image_manager = ImageManager()
        self.timeline = TimelinePanel()
        self.qwen_lab = QwenVoiceLab()
        self.api_settings = ApiSettingsPanel(ROOT)
        self.image_generation = ImageGenerationPanel(self.state)
        self.image_studio = ImageStudioPanel(self.state)
        self.image_studio.image_changed.connect(self.on_image_changed)
        self.music_studio = MusicStudioPanel(self.state)
        self.music_studio.music_changed.connect(self.on_music_changed)
        self.assembly_studio = AssemblyStudioPanel(self.state)
        self.assembly_engine_panel = AssemblyEnginePanel(self.state)
        self.timeline_preview = TimelinePreviewPanel(self.state)
        self.timeline_preview.block_selected.connect(self.select_block)
        self.block_state_panel = BlockStatePanel(self.state)
        self.workflow_engine = WorkflowEnginePanel(self.state)
        self.workflow_engine.jump_to_block.connect(self.select_block)
        self.workflow_engine.request_voice.connect(self.workflow_generate_voice)
        self.workflow_engine.request_image.connect(self.workflow_open_image_studio)
        self.workflow_engine.request_music.connect(self.workflow_open_music_studio)
        self.workflow_engine.request_assembly.connect(self.workflow_open_assembly)
        self.v24_orchestrator = V24OrchestratorPanel(self.state)
        self.v24_orchestrator.set_callbacks(self.progress_callback, self.refresh_production_ui, lambda: self.provider_box.currentText())
        self.exports_text = QTextEdit()
        self.exports_text.setReadOnly(True)

        self.tabs = WorkspaceGroups()
        self.tabs.add_produce(self.workspace, "Block Workspace")
        self.tabs.add_project(self.timeline, "Timeline")
        self.tabs.add_control(self.v24_orchestrator, "V24 Orchestrator")
        self.tabs.add_control(self.queue_panel, "Old Queue")
        self.tabs.add_project(self.character_manager, "Characters")
        self.tabs.add_project(self.image_manager, "Images")
        self.tabs.add_produce(self.image_studio, "Image Studio")
        self.tabs.add_produce(self.music_studio, "Music Studio")
        self.tabs.add_project(self.assembly_studio, "Assembly Studio")
        self.tabs.add_project(self.assembly_engine_panel, "Assembly Engine")
        self.tabs.add_project(self.timeline_preview, "Timeline Preview")
        self.tabs.add_control(self.block_state_panel, "Block State")
        self.tabs.add_control(self.workflow_engine, "Production Queue")
        self.tabs.add_project(self.qwen_lab, "Qwen Voice Lab")
        self.tabs.add_ai(self.api_settings, "API Settings")
        self.tabs.add_ai(self.image_generation, "Image Generation")
        self.tabs.add_project(self.exports_text, "Exports")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.explorer = SceneExplorer()
        self.explorer.block_selected.connect(self.select_block)
        self.explorer.scene_selected.connect(self.select_scene)
        dock_left = QDockWidget("Scenes / Blocks")
        dock_left.setWidget(self.explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_left)

        self.assistant = AssistantPanel()
        self.assistant.build_clicked.connect(self.build_episode)
        self.assistant.next_clicked.connect(self.select_block)
        dock_assistant = QDockWidget("Local Production Assistant")
        dock_assistant.setWidget(self.assistant)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_assistant)

        self.cost_panel = CostPanel()
        self.cost_panel.estimate_clicked.connect(self.estimate_cost)
        dock_cost = QDockWidget("Cost Control")
        dock_cost.setWidget(self.cost_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_cost)

        self.inspector = SmartInspector()
        dock_inspector = QDockWidget("Episode / Block Details")
        dock_inspector.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_inspector)
        self.tabifyDockWidget(dock_assistant, dock_cost)
        self.tabifyDockWidget(dock_assistant, dock_inspector)
        dock_assistant.raise_()

    # ------------------------------------------------------------------ Project open/create
    def open_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(ROOT / "projects"),
            "Historical POV Project (*.hps)",
        )
        if path:
            self.open_project(Path(path))

    def open_project(self, path):
        self.db = self.service.open(path)
        self.state.set_project(self.db)
        self.project_label.setText(str(path))
        p = self.db.project()
        self.title_label.setText(p["title"] if p else "Historical POV Studio")
        self.production_controller = ProductionController(self.db)
        self.refresh_all()
        self.auto_select_first_block()

    def open_project_wizard(self):
        if not self.db:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Create New Historical POV Project",
                str(ROOT / "projects" / "new_project.hps"),
                "Historical POV Project (*.hps)",
            )
            if not path:
                return
            self.open_project(Path(path))

        dlg = ProjectWizardDialog(self.db, self)
        if dlg.exec() and getattr(dlg, "generated", False):
            generated_path = getattr(dlg, "generated_project_path", None)
            if generated_path:
                self.open_project(Path(generated_path))
            else:
                self.refresh_all()
                self.auto_select_first_block()

    def focus_v24_orchestrator(self):
        if hasattr(self.tabs, "focus_widget"):
            self.tabs.focus_widget(self.v24_orchestrator)

    def open_local_ai_split(self):
        self.focus_v24_orchestrator()
        if not self.db:
            QMessageBox.warning(self, "No project", "Open a project first, then paste the full script.")
            return
        if hasattr(self.v24_orchestrator, "import_script"):
            self.v24_orchestrator.import_script()

    # ------------------------------------------------------------------ Refresh/select
    def current_cost_info(self):
        return cost_guard(self.db, self.mode_box.currentText(), self.provider_box.currentText()) if self.db else None

    def refresh_all(self):
        if not self.db:
            return
        counts = self.db.counts()
        for name, card in self.cards.items():
            value = counts.get(name, 0)
            if name == "complete":
                value = f"{self.db.completion_percent()}%"
            card.set_value(value)

        self.mission.refresh(self.db)
        self.explorer.populate(self.db)
        self.queue_panel.populate(self.db)
        self.character_manager.populate(self.db)
        self.image_manager.populate(self.db)
        self.timeline.populate(self.db)
        self.assistant.refresh(self.db, self.current_cost_info())

        for panel in [
            self.image_studio,
            self.music_studio,
            self.assembly_studio,
            self.block_state_panel,
            self.workflow_engine,
            self.v24_orchestrator,
            self.timeline_preview,
        ]:
            try:
                panel.refresh()
            except TypeError:
                pass
            except Exception:
                pass

        try:
            self.timeline_preview.load(self.db.timeline_rows())
        except Exception:
            pass

    def refresh_production_ui(self):
        self.refresh_all()
        if self.selected_block_id and self.db and self.db.block(self.selected_block_id):
            self.select_block(self.selected_block_id)

    def refresh_current_block_fast_v27(self):
        if self.selected_block_id and self.db and self.db.block(self.selected_block_id):
            self.select_block(self.selected_block_id)
        try:
            self.assistant.refresh(self.db, self.current_cost_info())
            self.mission.refresh(self.db)
            self.explorer.populate(self.db)
        except Exception:
            pass

    def auto_select_first_block(self):
        if not self.db:
            return
        if self.selected_block_id and self.db.block(self.selected_block_id):
            self.select_block(self.selected_block_id)
            return
        rows = self.db.blocks()
        if rows:
            self.select_block(rows[0]["id"])

    def select_scene(self, scene_id: str):
        # Keep for SceneExplorer compatibility. First block in scene becomes selected if available.
        if not self.db:
            return
        row = self.db.one("SELECT id FROM blocks WHERE scene_id=? ORDER BY sort_order LIMIT 1", (scene_id,))
        if row:
            self.select_block(row["id"])

    def select_block(self, block_id: str):
        if not self.db or not block_id:
            return
        block = self.db.block_with_scene(block_id)
        if not block:
            return
        self.selected_block_id = block_id
        self.state.set_selected_block(block_id)

        characters = [r["id"] for r in self.db.characters()]
        voice_states = [r["id"] for r in self.db.query("SELECT * FROM voice_states ORDER BY id")]
        self.workspace.set_dropdowns(characters, voice_states)
        self.workspace.load_block(block, self.db.audio_versions(block_id), db_root=self.db.root_dir, db=self.db)
        try:
            self.inspector.load(self.db, block_id)
        except Exception:
            pass

    # ------------------------------------------------------------------ Production actions
    def confirm_paid_if_needed(self):
        info = self.current_cost_info()
        if not info:
            return True
        if info.get("allowed", True):
            return True
        QMessageBox.warning(self, "Generation blocked", info.get("reason", "Paid generation is not allowed."))
        return False

    def open_generate_voice_dialog(self):
        if not self.db or not self.selected_block_id:
            QMessageBox.warning(self, "No block selected", "Select a block first.")
            return
        dlg = GenerateVoiceDialog(self, self.db, self.selected_block_id, self.provider_box.currentText())
        if dlg.exec():
            self.assistant.append_log(f"Generated voice for {self.selected_block_id}")
            self.refresh_current_block_fast_v27()

    def generate_single_block(self, block_id):
        if not self.db:
            return
        provider = self.provider_box.currentText()
        try:
            if provider == "mock":
                result = generate_voice_for_block(self.db, block_id, provider="mock")
                self.assistant.append_log(f"Generated mock voice for {block_id}: {result['audio_rel_path']}")
            else:
                BuildPipeline(self.db, provider_name=provider, progress=self.progress_callback).provider.synthesize(db=self.db, block_id=block_id)
                self.assistant.append_log(f"Generated voice for {block_id}")
            self.refresh_current_block_fast_v27()
        except Exception as exc:
            self.assistant.append_log("GENERATE FAILED: " + str(exc))
            QMessageBox.warning(self, "Generate failed", str(exc))

    def v28_plan_media(self):
        """Create visual-slot and scene-music plans without generating voice."""
        if not self.db:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V28 Visual Slot Planner",
            "How many total images/visual slots for the whole video?\nRecommended: 10–20. Default: 15.",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return
        try:
            report = plan_v28_media(self.db, visual_slots=slots)
            QMessageBox.information(
                self,
                "Media Plans Created",
                f"Visual slots: {report['visual_slots']}\n"
                f"Scene music cues: {report['scene_music']}\n\n"
                f"Visual plan:\n{report['visual_plan']}\n\n"
                f"Music plan:\n{report['music_plan']}",
            )
            self.assistant.append_log(f"V28 planned {report['visual_slots']} visual slots and {report['scene_music']} scene music cues")
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Plan Failed", str(exc))

    def v27_generate_missing_assets(self):
        """V28 batch: voices per block, images as visual slots, music per scene."""
        if not self.db:
            return
        voice_limit, ok = QInputDialog.getInt(
            self,
            "V28 Batch Production",
            "How many missing VOICE blocks to generate?\n0 = all missing voices.\nImages are NOT per block anymore.",
            5,
            0,
            100000,
            1,
        )
        if not ok:
            return
        visual_slots, ok = QInputDialog.getInt(
            self,
            "V28 Visual Slots",
            "How many total images/visual slots for the whole episode?\nUse 15 for your normal workflow. Use 3 for a small test.",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return

        provider = self.provider_box.currentText()
        real_limit = None if voice_limit == 0 else voice_limit
        maximum = max(1, (real_limit or len(self.db.blocks())) + visual_slots + len(self.db.scenes()))
        progress = QProgressDialog("Starting V28 batch production...", "Cancel", 0, maximum, self)
        progress.setWindowTitle("V28 Batch Production")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("Batch production cancelled by user.")

        try:
            report = run_batch_production(
                self.db,
                provider=provider,
                generate_voice=True,
                generate_images=True,
                generate_music=True,
                limit=real_limit,
                visual_slots=visual_slots,
                progress=progress_cb,
            )
            progress.setValue(progress.maximum())
            lines = [f"{step['step']}: {step['generated']}" for step in report["steps"]]
            QMessageBox.information(
                self,
                "V28 Batch Production Complete",
                "Generated / updated:\n" + "\n".join(lines)
                + "\n\nPolicy:\nVoice = per block\nImages = visual slots\nMusic = per scene"
                + f"\n\nReport:\n{report['report_path']}",
            )
            self.assistant.append_log("V28 batch complete: " + ", ".join(lines))
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Batch Production Failed", str(exc))
        finally:
            progress.close()


    def v31_asset_library(self):
        """Normalize V31 asset library: visual slot folders, scene music folders, placeholders, pointers."""
        if not self.db:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V31 Asset Library",
            "How many visual slots should exist for this episode?\nUse 15 normally, 3 for testing.",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return
        try:
            report = normalize_project_assets(self.db, visual_slots=slots, create_placeholders=True)
            msg = (
                f"Asset library normalized.\n\n"
                f"Voice approved: {report['voice']['approved']}/{report['voice']['total_blocks']}\n"
                f"Visual slots: {report['visual_slots']['approved_or_placeholder']}/{report['visual_slots']['total']}\n"
                f"Scene music: {report['scene_music']['approved_or_placeholder']}/{report['scene_music']['total']}\n\n"
                f"File:\n{report['asset_library_path']}"
            )
            QMessageBox.information(self, "V31 Asset Library", msg)
            self.assistant.append_log(
                f"V31 asset library: visuals {report['visual_slots']['approved_or_placeholder']}/{report['visual_slots']['total']}, "
                f"music {report['scene_music']['approved_or_placeholder']}/{report['scene_music']['total']}"
            )
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Asset Library Failed", str(exc))

    def v31_preview_timeline(self):
        """Build full timeline preview HTML/CSV over every block."""
        if not self.db:
            return
        try:
            preview = build_v31_timeline_preview(self.db, visual_slots=15)
            QMessageBox.information(
                self,
                "V31 Timeline Preview",
                f"Timeline preview created.\n\n"
                f"Blocks: {preview['total_blocks']}\n"
                f"Ready blocks: {preview['ready_blocks']}\n\n"
                f"HTML:\n{preview['html']}\n\nCSV:\n{preview['csv']}"
            )
            self.assistant.append_log(f"V31 preview: {preview['ready_blocks']}/{preview['total_blocks']} ready")
            try:
                os.startfile(preview['html'])
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Preview Failed", str(exc))

    def v29_build_timeline(self):
        """Build production/timeline.json from approved voice, visual slots, and scene music."""
        if not self.db:
            return
        try:
            timeline = build_timeline(self.db)
            QMessageBox.information(
                self,
                "V29 Timeline Built",
                f"Timeline created.\n\n"
                f"Blocks: {timeline['total_blocks']}\n"
                f"Ready blocks: {timeline['ready_blocks']}\n"
                f"Runtime: {timeline['runtime_minutes']} min\n\n"
                f"File:\n{self.db.root_dir / 'production' / 'timeline.json'}",
            )
            self.assistant.append_log(f"V29 timeline built: {timeline['ready_blocks']}/{timeline['total_blocks']} ready")
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Timeline Build Failed", str(exc))

    def v29_health_report(self):
        """Write and show V31 project health report."""
        if not self.db:
            return
        try:
            report = create_v31_health_report(self.db)
            msg = (
                f"Voice: {report['voice']['done']}/{report['voice']['total']} ({report['voice']['percent']}%)\n"
                f"Visual slots: {report['visual_slots']['done']}/{report['visual_slots']['total']} ({report['visual_slots']['percent']}%)\n"
                f"Scene music: {report['scene_music']['done']}/{report['scene_music']['total']} ({report['scene_music']['percent']}%)\n"
                f"Timeline: {report['timeline']['ready_blocks']}/{report['timeline']['total_blocks']} ready | {report['timeline']['runtime_minutes']} min\n"
                f"Preview HTML: {report['preview']['html']}\n"
                f"Assembly block manifests: {report['assembly']['block_manifests']}\n"
                f"Scene manifests: {report['assembly']['scene_manifests']}\n"
                f"Full block coverage: {report['assembly']['full_block_coverage']}\n"
                f"V31 package: {report['package']['v31_package_manifest']}\n\n"
                f"Next: {report['next_recommendation']['message']}\n\n"
                f"File:\n{self.db.root_dir / 'production' / 'health_report_latest.json'}"
            )
            QMessageBox.information(self, "V31 Project Health", msg)
            self.assistant.append_log("V31 health: " + report['next_recommendation']['message'])
            self.refresh_production_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Health Report Failed", str(exc))


    def v33_build_render_package(self):
        """Build V33 real-media FFmpeg render package without running the full render."""
        if not self.db:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V33 Real Media Render Package",
            "How many visual slots should be normalized for the render package?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return
        try:
            report = build_v33_render_package(self.db, visual_slots=slots)
            cov = report.get("coverage", {})
            QMessageBox.information(
                self,
                "V33 Render Package Ready",
                f"Real-media render package created.\n\n"
                f"Blocks: {report.get('total_blocks')}\n"
                f"Real voice blocks: {cov.get('real_voice_blocks')}\n"
                f"Real visual blocks: {cov.get('real_visual_blocks')}\n"
                f"Real music blocks: {cov.get('real_music_blocks')}\n"
                f"Final-ready blocks: {cov.get('final_ready_blocks')}\n\n"
                f"Folder:\n{report.get('render_dir')}\n\n"
                f"Report:\n{report.get('report_path')}",
            )
            self.assistant.append_log(f"V33 render package ready: {report.get('total_blocks')} block jobs")
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V33 RENDER PACKAGE FAILED: " + str(exc))
            QMessageBox.warning(self, "V33 Render Package Failed", str(exc))

    def v33_render_test_mp4(self):
        """Render a short V33 real-media MP4 preview using FFmpeg."""
        if not self.db:
            return
        blocks, ok = QInputDialog.getInt(
            self,
            "V33 Test MP4 Render",
            "How many starting blocks should be rendered now?\nUse 3 for fast testing.",
            3,
            1,
            50,
            1,
        )
        if not ok:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V33 Visual Slots",
            "How many visual slots should exist while preparing the test render?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return

        progress = QProgressDialog("Starting V33 real-media test render...", "Cancel", 0, blocks + 1, self)
        progress.setWindowTitle("V33 Render Test MP4")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V33 render cancelled by user.")

        try:
            report = render_v33_test_mp4(self.db, block_limit=blocks, visual_slots=slots, progress=progress_cb)
            progress.setValue(progress.maximum())
            modes = ", ".join(sorted(set(m.get("mode", "") for m in report.get("render_modes", []))))
            QMessageBox.information(
                self,
                "V33 Test MP4 Rendered",
                f"Rendered {report.get('blocks_rendered')} block(s).\n"
                f"Modes: {modes}\n\n"
                f"MP4:\n{report.get('output')}\n\n"
                f"Report:\n{report.get('report_path')}",
            )
            self.assistant.append_log(f"✓ V33 test MP4 rendered: {report.get('output')}")
            try:
                os.startfile(report.get('output'))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V33 TEST RENDER FAILED: " + str(exc))
            QMessageBox.warning(self, "V33 Test Render Failed", str(exc))
        finally:
            progress.close()





    def v37_voice_provider_health(self):
        """V37: provider/tool health for Qwen/Ollama, Piper, mock and voice progress."""
        if not self.db:
            return
        try:
            report = build_v37_voice_provider_health(self.db)
            s = report.get("summary", {})
            ollama = report.get("ollama", {})
            tools = report.get("tools", {})
            msg = (
                "V37 Voice Provider Health\n\n"
                f"Provider chain: {' -> '.join(report.get('provider_chain', []))}\n"
                f"Ollama: {'available' if ollama.get('available') else 'not available'}\n"
                f"Model found: {'yes' if ollama.get('model_found') else 'no'}\n"
                f"Piper: {'available' if tools.get('piper', {}).get('available') else 'not configured'}\n"
                f"Mock: available\n\n"
                f"Approved: {s.get('approved')}/{s.get('blocks_total')}\n"
                f"Waiting review: {s.get('waiting_review')}\n"
                f"Needs generation: {s.get('needs_generation')}\n"
                f"Pending chars: {s.get('pending_chars')}\n\n"
                "Important: Qwen is not a TTS engine. It can create voice direction only.\n"
                "Use piper/mock as audio providers.\n\n"
                f"Dashboard:\n{report.get('html_path')}"
            )
            QMessageBox.information(self, "V37 Voice Providers", msg)
            self.assistant.append_log(
                f"V37 providers: ollama={'yes' if ollama.get('available') else 'no'}, "
                f"piper={'yes' if tools.get('piper', {}).get('available') else 'no'}, "
                f"approved {s.get('approved')}/{s.get('blocks_total')}"
            )
            try:
                os.startfile(report.get("html_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V37 PROVIDER HEALTH FAILED: " + str(exc))
            QMessageBox.warning(self, "V37 Voice Providers Failed", str(exc))

    def v37_test_voice_provider(self):
        """V37: quick provider test without touching the production queue."""
        if not self.db:
            return
        default_chain = ",".join(provider_chain_from_env_v37(self.db.root_dir))
        chain_text, ok = QInputDialog.getText(
            self,
            "V37 Test Voice Provider Chain",
            "Provider order, comma separated.\nRecommended for real local TTS: qwen,piper,mock\nSafe test: qwen,mock",
            text=default_chain,
        )
        if not ok:
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "V37 Test Voice Text",
            "Text to synthesize/test:",
            "The flies always found us first. Long before Hannibal. Long before the screaming.",
        )
        if not ok or not text.strip():
            return
        chain = [x.strip().lower() for x in chain_text.replace(";", ",").split(",") if x.strip()]
        try:
            report = test_v37_voice_provider(self.db, text.strip(), provider_chain=chain)
            msg = (
                "V37 Voice Provider Test\n\n"
                f"Provider chain: {' -> '.join(report.get('provider_chain', []))}\n"
                f"Chosen provider: {report.get('chosen_provider') or 'none'}\n"
                f"Audio: {report.get('audio_path') or report.get('audio_rel_path') or 'none'}\n\n"
                f"Report:\n{report.get('report_path')}"
            )
            QMessageBox.information(self, "V37 Voice Test", msg)
            self.assistant.append_log(f"V37 voice test: provider={report.get('chosen_provider')}, audio={report.get('audio_rel_path')}")
            if report.get("audio_path"):
                try:
                    os.startfile(report.get("audio_path"))
                except Exception:
                    pass
        except Exception as exc:
            self.assistant.append_log("V37 VOICE TEST FAILED: " + str(exc))
            QMessageBox.warning(self, "V37 Voice Test Failed", str(exc))

    def v37_generate_voice_queue(self):
        """V37: generate queue with qwen as voice-direction provider and real TTS backups."""
        if not self.db:
            return
        default_chain = ",".join(provider_chain_from_env_v37(self.db.root_dir))
        chain_text, ok = QInputDialog.getText(
            self,
            "V37 Voice Provider Chain",
            "Provider order, comma separated.\nQwen creates direction only; Piper or another TTS must create real WAV.\nRecommended now: qwen,piper,mock\nSafe test if Piper is not installed: qwen,mock",
            text=default_chain,
        )
        if not ok:
            return
        chain = [x.strip().lower() for x in chain_text.replace(";", ",").split(",") if x.strip()]
        if not chain:
            chain = ["qwen", "mock"]
        limit, ok = QInputDialog.getInt(
            self,
            "V37 Generate Voice Queue",
            "How many missing/non-approved voice blocks to generate?\nUse 3 for test. 0 = all pending.",
            3,
            0,
            100000,
            1,
        )
        if not ok:
            return
        real_limit = None if limit == 0 else limit
        total_hint = real_limit or len(self.db.blocks())
        progress = QProgressDialog("Starting V37 voice queue...", "Cancel", 0, max(1, total_hint), self)
        progress.setWindowTitle("V37 Voice Queue")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V37 voice queue cancelled by user.")

        try:
            report = generate_v37_voice_queue(self.db, limit=real_limit, provider_chain=chain, progress=progress_cb)
            progress.setValue(progress.maximum())
            QMessageBox.information(
                self,
                "V37 Voice Queue Complete",
                f"Requested blocks: {report.get('requested_blocks')}\n"
                f"Generated blocks: {report.get('generated_blocks')}\n"
                f"Failed blocks: {report.get('failed_blocks')}\n\n"
                f"Provider chain: {' -> '.join(report.get('provider_chain', []))}\n\n"
                f"Report:\n{report.get('report_path')}\n\n"
                f"Dashboard:\n{report.get('dashboard_path')}",
            )
            self.assistant.append_log(
                f"V37 voice queue: generated {report.get('generated_blocks')}, failed {report.get('failed_blocks')}"
            )
            try:
                os.startfile(report.get("dashboard_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V37 VOICE QUEUE FAILED: " + str(exc))
            QMessageBox.warning(self, "V37 Voice Queue Failed", str(exc))
        finally:
            progress.close()


    def v36_voiceover_plan(self):
        """Build/open the V36 voiceover dashboard: Qwen primary, backups, approved/pending queue."""
        if not self.db:
            return
        try:
            chain = provider_chain_from_env(self.db.root_dir)
            report = build_v36_voiceover_plan(self.db, provider_chain=chain)
            s = report.get("summary", {})
            msg = (
                f"V36 Voiceover Plan\n\n"
                f"Provider chain: {' -> '.join(report.get('provider_chain', []))}\n"
                f"Approved voices: {s.get('voices_approved')}/{s.get('blocks_total')}\n"
                f"Generated waiting review: {s.get('generated_waiting_review')}\n"
                f"Missing generation: {s.get('missing_generation')}\n"
                f"Pending chars: {s.get('chars_pending')}\n\n"
                f"Qwen note:\n{s.get('qwen_note')}\n\n"
                f"Dashboard:\n{report.get('html_path')}"
            )
            QMessageBox.information(self, "V36 Voiceover Plan", msg)
            self.assistant.append_log(
                f"V36 voiceover plan: approved {s.get('voices_approved')}/{s.get('blocks_total')}, chain {' -> '.join(report.get('provider_chain', []))}"
            )
            try:
                os.startfile(report.get("html_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V36 VOICEOVER PLAN FAILED: " + str(exc))
            QMessageBox.warning(self, "V36 Voiceover Plan Failed", str(exc))

    def v36_generate_voice_queue(self):
        """Generate missing voices using Qwen first, then configured backups."""
        if not self.db:
            return
        default_chain = ",".join(provider_chain_from_env(self.db.root_dir))
        chain_text, ok = QInputDialog.getText(
            self,
            "V36 Voice Provider Chain",
            "Provider order, comma separated.\nRecommended now: qwen,mock\nLater: qwen,elevenlabs,openai,mock",
            text=default_chain,
        )
        if not ok:
            return
        chain = [x.strip().lower() for x in chain_text.replace(";", ",").split(",") if x.strip()]
        if not chain:
            chain = ["qwen", "mock"]
        limit, ok = QInputDialog.getInt(
            self,
            "V36 Generate Voice Queue",
            "How many missing/non-approved voice blocks to generate?\nUse 3 for test. 0 = all pending.",
            3,
            0,
            100000,
            1,
        )
        if not ok:
            return
        real_limit = None if limit == 0 else limit
        total_hint = real_limit or len(self.db.blocks())
        progress = QProgressDialog("Starting V36 voice queue...", "Cancel", 0, max(1, total_hint), self)
        progress.setWindowTitle("V36 Voice Queue")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V36 voice queue cancelled by user.")

        try:
            report = generate_v36_voice_queue(self.db, limit=real_limit, provider_chain=chain, progress=progress_cb)
            progress.setValue(progress.maximum())
            QMessageBox.information(
                self,
                "V36 Voice Queue Complete",
                f"Requested blocks: {report.get('requested_blocks')}\n"
                f"Generated blocks: {report.get('generated_blocks')}\n"
                f"Failed blocks: {report.get('failed_blocks')}\n\n"
                f"Provider chain: {' -> '.join(report.get('provider_chain', []))}\n\n"
                f"Report:\n{report.get('report_path')}\n\n"
                f"Review queue:\n{report.get('review_html_path')}",
            )
            self.assistant.append_log(
                f"V36 voice queue: generated {report.get('generated_blocks')}, failed {report.get('failed_blocks')}"
            )
            try:
                os.startfile(report.get("review_html_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V36 VOICE QUEUE FAILED: " + str(exc))
            QMessageBox.warning(self, "V36 Voice Queue Failed", str(exc))
        finally:
            progress.close()

    def v35_dashboard(self):
        """Build and open the V35 production dashboard: real readiness, rendered blocks, final episode status."""
        if not self.db:
            return
        try:
            report = build_v35_dashboard(self.db)
            summary = report.get("summary", {})
            msg = (
                f"V35 Production Dashboard\n\n"
                f"Voices: {summary.get('voices_approved')}/{summary.get('blocks_total')}\n"
                f"Visual slots: {summary.get('visual_slots_approved')}/{summary.get('visual_slots_total')}\n"
                f"Scene music: {summary.get('scene_music_approved')}/{summary.get('scene_music_total')}\n"
                f"Renderable blocks: {summary.get('renderable_blocks')}/{summary.get('blocks_total')}\n"
                f"Rendered blocks: {summary.get('rendered_blocks')}/{summary.get('blocks_total')}\n"
                f"Final-ready blocks: {summary.get('final_ready_blocks')}/{summary.get('blocks_total')}\n"
                f"Episode exists: {summary.get('episode_exists')}\n\n"
                f"Next:\n{summary.get('next_action')}\n\n"
                f"Dashboard:\n{report.get('html_path')}"
            )
            QMessageBox.information(self, "V35 Dashboard", msg)
            self.assistant.append_log("V35 dashboard: " + str(summary.get("next_action", "")))
            try:
                os.startfile(report.get("html_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V35 DASHBOARD FAILED: " + str(exc))
            QMessageBox.warning(self, "V35 Dashboard Failed", str(exc))

    def v35_review_queue(self):
        """Build the V35 review queue and jump to the first actionable block."""
        if not self.db:
            return
        try:
            report = build_v35_review_queue(self.db)
            msg = (
                f"Review queue created.\n\n"
                f"Items: {report.get('total_items')}\n"
                f"First block: {report.get('first_block_id') or 'none'}\n\n"
                f"HTML:\n{report.get('html_path')}\n\n"
                f"CSV:\n{report.get('csv_path')}"
            )
            QMessageBox.information(self, "V35 Review Queue", msg)
            self.assistant.append_log(f"V35 review queue: {report.get('total_items')} items")
            first = report.get("first_block_id")
            if first:
                self.select_block(first)
            try:
                os.startfile(report.get("html_path"))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V35 REVIEW QUEUE FAILED: " + str(exc))
            QMessageBox.warning(self, "V35 Review Queue Failed", str(exc))

    def v35_open_episode(self):
        """Open the latest rendered episode MP4 if it exists."""
        if not self.db:
            return
        try:
            path = latest_episode_path(self.db)
            if not path:
                QMessageBox.information(self, "Open Episode", "No rendered episode MP4 found yet. Run Render Episode first.")
                return
            self.assistant.append_log("Opening episode: " + path)
            os.startfile(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Episode Failed", str(exc))

    def v34_build_full_package(self):
        """Build V34 full episode render package without rendering the episode."""
        if not self.db:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V34 Full Episode Package",
            "How many visual slots should exist for the full episode package?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return
        try:
            report = build_v34_full_episode_package(self.db, visual_slots=slots)
            QMessageBox.information(
                self,
                "V34 Package Ready",
                f"Full episode render package created.\n\n"
                f"Blocks: {report.get('total_blocks')}\n"
                f"Render folder:\n{report.get('render_dir')}\n\n"
                f"Episode target:\n{report.get('episode_mp4')}\n\n"
                f"Report:\n{report.get('report_path')}",
            )
            self.assistant.append_log(f"V34 package ready: {report.get('total_blocks')} blocks")
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V34 PACKAGE FAILED: " + str(exc))
            QMessageBox.warning(self, "V34 Package Failed", str(exc))

    def v34_render_full_episode(self):
        """Render a resumable V34 episode MP4. Use a small block count first for testing."""
        if not self.db:
            return
        blocks, ok = QInputDialog.getInt(
            self,
            "V34 Episode Render",
            "How many blocks should be rendered?\n0 = FULL EPISODE.\nFor first test use 5 or 10.",
            10,
            0,
            100000,
            1,
        )
        if not ok:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V34 Visual Slots",
            "How many visual slots should exist while preparing the render?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return

        max_blocks = None if blocks == 0 else blocks
        expected = (max_blocks or len(self.db.blocks())) + 1
        progress = QProgressDialog("Starting V34 episode render...", "Cancel", 0, max(1, expected), self)
        progress.setWindowTitle("V34 Full Episode Render")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V34 render cancelled by user.")

        try:
            report = render_v34_full_episode(
                self.db,
                visual_slots=slots,
                max_blocks=max_blocks,
                resume=True,
                force=False,
                progress=progress_cb,
            )
            progress.setValue(progress.maximum())
            if report.get("concat_ok"):
                QMessageBox.information(
                    self,
                    "V34 Episode Rendered",
                    f"Rendered/existing blocks: {report.get('rendered_or_existing_blocks')}\n"
                    f"Failed blocks: {report.get('failed_blocks')}\n\n"
                    f"MP4:\n{report.get('episode_mp4')}\n\n"
                    f"Report:\n{report.get('report_path')}",
                )
                self.assistant.append_log(f"✓ V34 episode rendered: {report.get('episode_mp4')}")
                try:
                    os.startfile(report.get("episode_mp4"))
                except Exception:
                    pass
            else:
                QMessageBox.warning(
                    self,
                    "V34 Render Incomplete",
                    f"Render did not complete.\n"
                    f"Rendered/existing blocks: {report.get('rendered_or_existing_blocks')}\n"
                    f"Failed blocks: {report.get('failed_blocks')}\n\n"
                    f"Logs:\n{report.get('logs_dir')}\n\n"
                    f"Report:\n{report.get('report_path')}",
                )
                self.assistant.append_log("V34 render incomplete; check report/logs")
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V34 RENDER FAILED: " + str(exc))
            QMessageBox.warning(self, "V34 Render Failed", str(exc))
        finally:
            progress.close()

    def v32_build_render_package(self):
        """Build FFmpeg-ready V32 render package without running the full render."""
        if not self.db:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V32 Render Package",
            "How many visual slots should be normalized for the render package?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return
        try:
            report = build_v32_render_package(self.db, visual_slots=slots)
            QMessageBox.information(
                self,
                "V32 Render Package Ready",
                f"FFmpeg render package created.\n\n"
                f"Blocks: {report.get('total_blocks')}\n"
                f"Runtime: {report.get('runtime_minutes')} min\n\n"
                f"Folder:\n{report.get('render_dir')}\n\n"
                f"Report:\n{report.get('report_path')}",
            )
            self.assistant.append_log(f"V32 render package ready: {report.get('total_blocks')} block jobs")
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V32 RENDER PACKAGE FAILED: " + str(exc))
            QMessageBox.warning(self, "V32 Render Package Failed", str(exc))

    def v32_render_test_mp4(self):
        """Render a short real MP4 preview using FFmpeg."""
        if not self.db:
            return
        blocks, ok = QInputDialog.getInt(
            self,
            "V32 Test MP4 Render",
            "How many starting blocks should be rendered now?\nUse 3 for fast testing. Full episode render should use the generated BAT files later.",
            3,
            1,
            50,
            1,
        )
        if not ok:
            return
        slots, ok = QInputDialog.getInt(
            self,
            "V32 Visual Slots",
            "How many visual slots should exist while preparing the test render?",
            15,
            1,
            100,
            1,
        )
        if not ok:
            return

        progress = QProgressDialog("Starting V32 test render...", "Cancel", 0, blocks + 1, self)
        progress.setWindowTitle("V32 Render Test MP4")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V32 render cancelled by user.")

        try:
            report = render_v32_test_mp4(self.db, block_limit=blocks, visual_slots=slots, progress=progress_cb)
            progress.setValue(progress.maximum())
            QMessageBox.information(
                self,
                "V32 Test MP4 Rendered",
                f"Rendered {report.get('blocks_rendered')} block(s).\n\n"
                f"MP4:\n{report.get('output')}\n\n"
                f"Report:\n{report.get('report_path')}",
            )
            self.assistant.append_log(f"✓ V32 test MP4 rendered: {report.get('output')}")
            try:
                os.startfile(report.get('output'))
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V32 TEST RENDER FAILED: " + str(exc))
            QMessageBox.warning(self, "V32 Test Render Failed", str(exc))
        finally:
            progress.close()

    def build_episode(self):
        """V31 Build Package: normalize assets, preview, full manifests, subtitles, CapCut CSV, package."""
        if not self.db:
            return

        maximum = 8
        progress = QProgressDialog("Starting V31 package build...", "Cancel", 0, maximum, self)
        progress.setWindowTitle("V31 Execution Preview Package")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        counter = {"n": 0}

        def progress_cb(asset_type, item_id, _i, _total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {item_id}")
            progress.setValue(min(counter["n"], progress.maximum()))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("V31 build cancelled by user.")

        self.assistant.append_log("V31 BUILD PACKAGE STARTED")
        try:
            report = build_v31_production_package(self.db, visual_slots=15, progress=progress_cb)
            progress.setValue(progress.maximum())
            preview = report.get("preview", {})
            assembly = report.get("assembly", {})
            package = report.get("package", {})
            QMessageBox.information(
                self,
                "V31 Package Complete",
                "Created V31 execution/preview package.\n\n"
                f"Blocks: {assembly.get('total_blocks', '')}\n"
                f"Ready: {assembly.get('ready_blocks', '')}\n"
                f"Block manifests: {assembly.get('block_manifests', '')}\n"
                f"Scene manifests: {assembly.get('scene_manifests', '')}\n"
                f"Preview: {preview.get('html', '')}\n"
                f"Package: {package.get('package_dir', '')}\n\n"
                f"Report:\n{report.get('report_path', '')}",
            )
            self.assistant.append_log(
                f"✓ V31 package complete: {assembly.get('block_manifests', 0)} block manifests, "
                f"{assembly.get('scene_manifests', 0)} scene manifests, preview + package ready"
            )
            try:
                html = preview.get('html')
                if html:
                    os.startfile(html)
            except Exception:
                pass
            self.refresh_production_ui()
        except Exception as exc:
            self.assistant.append_log("V31 BUILD STOPPED: " + str(exc))
            QMessageBox.warning(self, "V31 Build stopped", str(exc))
        finally:
            progress.close()

    def approve_latest(self):
        if not self.selected_block_id:
            return
        try:
            rel = BuildPipeline(self.db, provider_name="mock").approve_latest(self.selected_block_id)
            self.assistant.append_log(f"Approved voice {self.selected_block_id}: {rel}")
            self.refresh_current_block_fast_v27()
        except Exception as exc:
            QMessageBox.critical(self, "Approve failed", str(exc))

    def mark_redo(self):
        if not self.selected_block_id:
            return
        reason, ok = QInputDialog.getText(self, "Redo", "Reason:")
        if ok:
            self.service.set_block_status(self.selected_block_id, "redo", reason)
            self.refresh_current_block_fast_v27()

    def reject_block(self):
        if not self.selected_block_id:
            return
        reason, ok = QInputDialog.getText(self, "Reject", "Reason:")
        if ok:
            self.service.set_block_status(self.selected_block_id, "rejected", reason)
            self.refresh_current_block_fast_v27()

    def save_block(self):
        if not self.selected_block_id:
            return
        data = self.workspace.get_edit_data()
        self.service.save_block(
            self.selected_block_id,
            data["character_id"],
            data["voice_state_id"],
            data["scene_label"],
            data["text"],
            data["image_prompt"],
            data["music_cue"],
            data["notes"],
        )
        self.assistant.append_log(f"Saved {self.selected_block_id}")
        self.refresh_current_block_fast_v27()

    def set_image_status(self, status):
        if not self.selected_block_id:
            return
        self.service.set_image_status(self.selected_block_id, status)
        self.assistant.append_log(f"Image {self.selected_block_id}: {status}")
        self.refresh_current_block_fast_v27()

    def set_music_status(self, status):
        if not self.selected_block_id:
            return
        self.service.set_music_status(self.selected_block_id, status)
        self.assistant.append_log(f"Music {self.selected_block_id}: {status}")
        self.refresh_current_block_fast_v27()

    def progress_callback(self, i, total, block_id, message=""):
        try:
            self.queue_panel.set_progress(i, total, block_id, message)
            QApplication.processEvents()
        except Exception:
            pass

    def open_next_production_task(self):
        if not self.db:
            return
        try:
            report = create_v30_health_report(self.db)
            task = report.get("next_recommendation", {})
            message = task.get("message", "No recommendation.")
            code = task.get("task", "")
            self.assistant.append_log("NEXT: " + message)

            if code == "generate_missing_voices":
                nxt = self.db.next_recommended_block()
                if nxt:
                    self.select_block(nxt["id"])
            elif code in {"visual_slots", "scene_music"}:
                self.v28_plan_media()
            elif code == "build_timeline":
                self.v29_build_timeline()
            elif code == "build_episode":
                self.build_episode()
            else:
                QMessageBox.information(self, "Next Task", message)
        except Exception:
            nxt = self.db.next_recommended_block()
            if not nxt:
                QMessageBox.information(self, "Next Task", "No pending block task found.")
                return
            self.select_block(nxt["id"])

    def estimate_cost(self):
        if not self.db:
            return
        info = self.current_cost_info()
        QMessageBox.information(
            self,
            "Cost Estimate",
            f"Provider: {info['provider']}\n"
            f"Mode: {info['mode']}\n"
            f"Blocks: {info['blocks']}\n"
            f"Characters: {info['chars']}\n"
            f"Estimated cost: ${info['estimated_cost']:.4f}\n"
            f"Allowed: {info['allowed']}\n"
            f"Reason: {info['reason']}",
        )

    def export_capcut(self, silent=False):
        if not self.db:
            return
        path = export_capcut_csv(self.db)
        self.exports_text.append(f"Exported: {path}")
        p = self.db.project()
        if p:
            self.db.execute("UPDATE project SET export_status='approved' WHERE id=?", (p["id"],))
        if not silent:
            QMessageBox.information(self, "Exported", f"CapCut CSV exported:\n{path}")
        self.refresh_all()

    def open_selected_version(self):
        if not self.db or not self.selected_block_id:
            QMessageBox.warning(self, "No block selected", "Select a block first.")
            return
        rel = ""
        if hasattr(self.workspace, "get_selected_version_path"):
            rel = self.workspace.get_selected_version_path()
        if not rel:
            QMessageBox.warning(self, "No version selected", "Select an audio version first.")
            return
        path = self.db.root_dir / rel
        if not path.exists():
            QMessageBox.warning(self, "Missing file", f"File not found:\n{path}")
            return
        os.startfile(str(path))

    def open_latest_audio(self):
        if not self.selected_block_id:
            return
        row = self.db.one(
            "SELECT * FROM audio_versions WHERE block_id=? ORDER BY version DESC LIMIT 1",
            (self.selected_block_id,),
        )
        if not row:
            QMessageBox.warning(self, "No audio", "No audio version yet.")
            return
        os.startfile(str(self.db.root_dir / row["path"]))

    # ------------------------------------------------------------------ Workflow panel callbacks
    def workflow_generate_voice(self, block_id: str):
        self.select_block(block_id)
        self.generate_single_block(block_id)

    def workflow_open_image_studio(self, block_id: str):
        self.select_block(block_id)
        self.tabs.focus_widget(self.image_studio)

    def workflow_open_music_studio(self, block_id: str):
        self.select_block(block_id)
        self.tabs.focus_widget(self.music_studio)

    def workflow_open_assembly(self):
        self.tabs.focus_widget(self.assembly_studio)

    def on_image_changed(self, block_id: str):
        if block_id:
            self.select_block(block_id)
        else:
            self.refresh_current_block_fast_v27()

    def on_music_changed(self, block_id: str):
        if block_id:
            self.select_block(block_id)
        else:
            self.refresh_current_block_fast_v27()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = StudioQt()
    win.show()
    sys.exit(app.exec())
