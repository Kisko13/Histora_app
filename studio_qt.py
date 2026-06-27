import os, sys
from pathlib import Path
from hps_qt.app_state import AppState
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QComboBox,QDockWidget,QTabWidget,QTextEdit,QToolBar,QInputDialog
from PySide6.QtCore import Qt
from hps.core.project_service import ProjectService
from hps.core.cost_control import cost_guard
from hps.pipeline.build import BuildPipeline
from hps.pipeline.export import export_capcut_csv
from hps_qt.widgets.stat_card import StatCard
from hps_qt.widgets.mission_control import MissionControl
from hps_qt.widgets.scene_explorer import SceneExplorer
from hps_qt.widgets.block_workspace import BlockWorkspace
from hps_qt.widgets.smart_inspector import SmartInspector
from hps_qt.widgets.queue_panel import QueuePanel
from hps_qt.widgets.assistant_panel import AssistantPanel
from hps_qt.widgets.cost_panel import CostPanel
from hps_qt.widgets.manager_panels import CharacterManager,ImageManager
from hps_qt.widgets.timeline_panel import TimelinePanel
from hps_qt.widgets.mission_dashboard import MissionDashboard
from hps_qt.widgets.workspace_groups import WorkspaceGroups
from hps_qt.widgets.workflow_engine_panel import WorkflowEnginePanel
from hps_qt.widgets.block_state_panel import BlockStatePanel
from hps_qt.widgets.assembly_studio_panel import AssemblyStudioPanel
from hps_qt.widgets.assembly_engine_panel import AssemblyEnginePanel
from hps_qt.widgets.timeline_preview_panel import TimelinePreviewPanel
from hps_qt.widgets.music_studio_panel import MusicStudioPanel
from hps_qt.widgets.image_studio_panel import ImageStudioPanel
from hps_qt.widgets.image_generation_panel import ImageGenerationPanel
from hps_qt.widgets.api_settings_panel import ApiSettingsPanel
from hps_qt.widgets.generate_voice_dialog import GenerateVoiceDialog
from hps.controllers.production_controller import ProductionController
from hps_qt.dialogs.production_dialog import ProductionDialog
from hps_qt.widgets.qwen_voice_lab import QwenVoiceLab
from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel
from hps_qt.dialogs.project_wizard import ProjectWizardDialog

ROOT=Path(__file__).resolve().parent
STYLE="""QMainWindow,QWidget{background:#1e1e1e;color:#e8e8e8;font-family:Segoe UI;font-size:10pt} QLabel{color:#e8e8e8} QPushButton{background:#3a3a3a;color:#e8e8e8;border:1px solid #555;padding:7px} QPushButton:hover{background:#4a4a4a} QComboBox,QLineEdit,QTextEdit,QListWidget{background:#151515;color:#e8e8e8;border:1px solid #444} QTreeWidget,QTableWidget{background:#151515;color:#e8e8e8;border:1px solid #444} QTabBar::tab{background:#2d2d30;color:#ddd;padding:8px 12px} QTabBar::tab:selected{background:#3a3a3a} QProgressBar{background:#151515;border:1px solid #444;text-align:center} QProgressBar::chunk{background:#4cc2ff} #StatCard,#InfoBadge,#Section{background:#252526;border:1px solid #333;border-radius:4px} #CardTitle,#BadgeTitle{color:#a0a0a0;font-size:9pt;font-weight:bold} #CardValue{color:#fff;font-size:24pt;font-weight:bold} #BadgeValue{color:#fff;font-size:13pt;font-weight:bold} #WorkspaceTitle{font-size:18pt;font-weight:bold} #PanelTitle{font-size:16pt;font-weight:bold} #AudioPlaceholder{background:#101010;border:1px solid #444;padding:18px;color:#a0a0a0} #Overview{color:#ddd;padding:6px} #SectionTitle{font-weight:bold;color:#4cc2ff}"""

class StudioQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Historical POV Studio v24 — Production Orchestrator")
        self.resize(1800,1060)
        self.service=ProjectService()
        self.db=None
        self.selected_block_id=None
        self.state=AppState()
        self.mission_dashboard=MissionDashboard(self.state)
        self.provider_box=QComboBox(); self.provider_box.addItems(["mock","qwen"])
        self.mode_box=QComboBox(); self.mode_box.addItems(["missing","redo","all"])
        self.build_ui()
        default=ROOT/"projects"/"cannae_001"/"cannae_001.hps"
        if default.exists(): self.open_project(default)

    def build_ui(self):
        tb=QToolBar("Main"); self.addToolBar(tb)
        for text,fn in [("Open",self.open_project_dialog),("New Project Wizard",self.open_project_wizard),("Paste Script / Local AI Split",self.open_local_ai_split),("V24 Orchestrator",self.focus_v24_orchestrator),("Generate Voice",self.open_generate_voice_dialog),("Build",self.build_episode),("Next Task",self.open_next_production_task),("Estimate Cost",self.estimate_cost),("Export",self.export_capcut)]:
            b=QPushButton(text); b.clicked.connect(fn); tb.addWidget(b)
        tb.addSeparator(); tb.addWidget(QLabel(" Provider ")); tb.addWidget(self.provider_box); tb.addWidget(QLabel(" Mode ")); tb.addWidget(self.mode_box)

        central=QWidget(); l=QVBoxLayout(central)
        self.title_label=QLabel("Historical POV Studio"); self.title_label.setStyleSheet("font-size:26pt;font-weight:bold")
        self.project_label=QLabel("No project loaded"); self.project_label.setStyleSheet("color:#a0a0a0")
        l.addWidget(self.title_label); l.addWidget(self.project_label)
        self.mission=MissionControl(); l.addWidget(self.mission)

        cards=QHBoxLayout(); self.cards={}
        for name in ["approved","generated","missing","redo","rejected","complete"]:
            card=StatCard(name,"0"); self.cards[name]=card; cards.addWidget(card)
        l.addLayout(cards)

        self.workspace=BlockWorkspace()
        if hasattr(self.workspace, 'generate_clicked'):
            self.workspace.generate_clicked.connect(self.open_generate_voice_dialog)
        self.workspace.approve_clicked.connect(self.approve_latest)
        self.workspace.redo_clicked.connect(self.mark_redo)
        self.workspace.reject_clicked.connect(self.reject_block)
        self.workspace.open_audio_clicked.connect(self.open_latest_audio)
        self.workspace.open_selected_version_clicked.connect(self.open_selected_version)
        self.workspace.generate_block_clicked.connect(self.generate_single_block)
        self.workspace.save_clicked.connect(self.save_block)
        self.workspace.image_approve_clicked.connect(lambda:self.set_image_status("approved"))
        self.workspace.image_redo_clicked.connect(lambda:self.set_image_status("redo"))
        self.workspace.music_approve_clicked.connect(lambda:self.set_music_status("approved"))

        self.queue_panel=QueuePanel(); self.character_manager=CharacterManager(); self.image_manager=ImageManager(); self.timeline=TimelinePanel(); self.qwen_lab=QwenVoiceLab(); self.api_settings=ApiSettingsPanel(ROOT); self.image_generation=ImageGenerationPanel(self.state); self.image_studio=ImageStudioPanel(self.state); self.image_studio.image_changed.connect(self.on_image_changed); self.music_studio=MusicStudioPanel(self.state); self.music_studio.music_changed.connect(self.on_music_changed); self.assembly_studio=AssemblyStudioPanel(self.state); self.assembly_engine_panel=AssemblyEnginePanel(self.state); self.timeline_preview=TimelinePreviewPanel(self.state); self.timeline_preview.block_selected.connect(self.select_block); self.block_state_panel=BlockStatePanel(self.state); self.workflow_engine=WorkflowEnginePanel(self.state); self.workflow_engine.jump_to_block.connect(self.select_block); self.workflow_engine.request_voice.connect(self.workflow_generate_voice); self.workflow_engine.request_image.connect(self.workflow_open_image_studio); self.workflow_engine.request_music.connect(self.workflow_open_music_studio); self.workflow_engine.request_assembly.connect(self.workflow_open_assembly); self.v24_orchestrator=V24OrchestratorPanel(self.state); self.v24_orchestrator.set_callbacks(self.progress_callback, self.refresh_production_ui, lambda: self.provider_box.currentText()); self.exports_text=QTextEdit(); self.exports_text.setReadOnly(True)

        tabs=WorkspaceGroups(); self.tabs=tabs
        tabs.add_produce(self.workspace,"Block Workspace")
        tabs.add_project(self.timeline,"Timeline")
        tabs.add_control(self.v24_orchestrator,"V24 Orchestrator")
        tabs.add_control(self.queue_panel,"Old Queue")
        tabs.add_project(self.character_manager,"Characters")
        tabs.add_project(self.image_manager,"Images")
        tabs.add_produce(self.image_studio,"Image Studio")
        tabs.add_produce(self.music_studio,"Music Studio")
        tabs.add_project(self.assembly_studio,"Assembly Studio")
        tabs.add_project(self.assembly_engine_panel,"Assembly Engine")
        tabs.add_project(self.timeline_preview,"Timeline Preview")
        tabs.add_control(self.block_state_panel,"Block State")
        tabs.add_control(self.workflow_engine,"Production Queue")
        tabs.add_project(self.qwen_lab,"Qwen Voice Lab")
        tabs.add_ai(self.api_settings,"API Settings")
        tabs.add_ai(self.image_generation,"Image Generation")
        tabs.add_project(self.exports_text,"Exports")
        l.addWidget(tabs,1); self.setCentralWidget(central)

        self.explorer=SceneExplorer(); self.explorer.block_selected.connect(self.select_block); self.explorer.scene_selected.connect(self.select_scene)
        dock_left=QDockWidget("Scenes / Blocks"); dock_left.setWidget(self.explorer); self.addDockWidget(Qt.LeftDockWidgetArea,dock_left)

        self.assistant=AssistantPanel(); self.assistant.build_clicked.connect(self.build_episode); self.assistant.next_clicked.connect(self.select_block)
        dock_assistant=QDockWidget("Local Production Assistant"); dock_assistant.setWidget(self.assistant); self.addDockWidget(Qt.RightDockWidgetArea,dock_assistant)

        self.cost_panel=CostPanel(); self.cost_panel.estimate_clicked.connect(self.estimate_cost)
        dock_cost=QDockWidget("Cost Control"); dock_cost.setWidget(self.cost_panel); self.addDockWidget(Qt.RightDockWidgetArea,dock_cost)

        self.inspector=SmartInspector()
        dock_inspector=QDockWidget("Episode / Block Details"); dock_inspector.setWidget(self.inspector); self.addDockWidget(Qt.RightDockWidgetArea,dock_inspector)
        self.tabifyDockWidget(dock_assistant,dock_cost); self.tabifyDockWidget(dock_assistant,dock_inspector); dock_assistant.raise_()

    def focus_v24_orchestrator(self):
        """Jump directly to Control -> V24 Orchestrator so the script splitter is not hidden."""
        if hasattr(self, "tabs") and hasattr(self.tabs, "focus_widget") and hasattr(self, "v24_orchestrator"):
            self.tabs.focus_widget(self.v24_orchestrator)

    def open_local_ai_split(self):
        """Top-toolbar shortcut: open the local/free full-script splitter immediately."""
        self.focus_v24_orchestrator()
        if not getattr(self, "db", None):
            QMessageBox.warning(self, "No project", "Open a project first, then paste the full script.")
            return
        if hasattr(self, "v24_orchestrator") and hasattr(self.v24_orchestrator, "import_script"):
            self.v24_orchestrator.import_script()

   

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
            generated_path = getattr(dlg, "generated_project_path", None)

            if generated_path:
                # Reopen the generated project so all main-studio panels refresh from disk.
                self.open_project(Path(generated_path))
            else:
                self.project_label.setText(str(self.db.path))
                p = self.db.project()
                self.title_label.setText(p["title"] if p else "Historical POV Studio")
                self.refresh_all()
                self.auto_select_first_block()

    def open_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(ROOT / "projects"),
            "Historical POV Project (*.hps)"
        )
        if path:
            self.open_project(Path(path))

    def open_project(self, path):
        self.db = self.service.open(path)
        self.state.set_project(self.db)
        self.project_label.setText(str(path))
        p = self.db.project()
        self.title_label.setText(p["title"] if p else "Historical POV Studio")
        self.refresh_all()
        self.auto_select_first_block()

    def current_cost_info(self):
        return cost_guard(self.db, self.mode_box.currentText(), self.provider_box.currentText()) if self.db else None

    def auto_select_first_block(self):
        if not self.db:
            return
        if self.selected_block_id and self.db.block(self.selected_block_id):
            self.select_block(self.selected_block_id)
            return
        rows = self.db.blocks()
        if rows:
            self.select_block(rows[0]["id"])

    def refresh_all(self):
        if not self.db: return
        info=self.current_cost_info(); self.refresh_cards(); self.mission.refresh(self.db); self.explorer.populate(self.db); self.queue_panel.populate(self.db); self.timeline.populate(self.db); self.assistant.refresh(self.db, info); self.character_manager.populate(self.db); self.image_manager.populate(self.db); self.image_studio.set_context(self.db, self.selected_block_id)
        self.v24_orchestrator.set_context(self.db)
        self.workspace.set_dropdowns([r["id"] for r in self.db.query("SELECT id FROM characters ORDER BY id")],[r["id"] for r in self.db.query("SELECT id FROM voice_states ORDER BY id")])
        self.image_generation.set_context(self.db, self.selected_block_id)
        self.cost_panel.set_info(f"""Provider: {info['provider']}
Mode: {info['mode']}
Blocks: {info['blocks']}
Characters: {info['chars']}
Estimated cost: ${info['estimated_cost']:.4f}
Paid generation enabled: {info['paid_enabled']}
Max build cost: ${info['max_cost']:.2f}

Local assistant uses no paid AI.""")
        if self.selected_block_id and self.db.block(self.selected_block_id): self.select_block(self.selected_block_id)
        else: self.inspector.show_project(self.db)
    def refresh_cards(self):
        c=self.db.counts(); self.cards["approved"].set_value(c.get("approved",0)); self.cards["generated"].set_value(c.get("generated",0)); self.cards["missing"].set_value(c.get("missing",0)); self.cards["redo"].set_value(c.get("redo",0)); self.cards["rejected"].set_value(c.get("rejected",0)); self.cards["complete"].set_value(str(self.db.completion_percent())+"%")
    def select_block(self,block_id):
        if not self.db or not block_id or not self.db.block(block_id):
            return
        self.selected_block_id=block_id; self.state.set_selected_block(block_id); block=self.db.block_with_scene(block_id); versions=self.db.audio_versions(block_id); self.workspace.load_block(block,versions,db_root=self.db.root_dir,db=self.db); self.inspector.show_block(block,versions)
    def select_scene(self,scene_id):
        scene=self.db.one("SELECT * FROM scenes WHERE id=?",(scene_id,))
        if scene: self.inspector.setPlainText(f"SCENE {scene['id']}\n\n{scene['title']}\n\n{scene['summary'] or ''}\n\nVisual: {scene['visual_theme']}\nMusic: {scene['music_profile']}\nSFX: {scene['sfx_profile']}")

    def refresh_production_ui(self):
        if not self.db:
            return
        self.refresh_cards()
        self.mission.refresh(self.db)
        self.explorer.populate(self.db)
        self.queue_panel.populate(self.db)
        self.timeline.populate(self.db)
        self.assistant.refresh(self.db, self.current_cost_info())
        self.mission_dashboard.refresh()
        self.image_manager.populate(self.db)
        self.assembly_studio.refresh()
        self.block_state_panel.refresh()
        self.workflow_engine.refresh()
        self.v24_orchestrator.set_context(self.db)
        self.v24_orchestrator.refresh()
        if self.selected_block_id and self.db.block(self.selected_block_id):
            block=self.db.block_with_scene(self.selected_block_id)
            versions=self.db.audio_versions(self.selected_block_id)
            self.workspace.load_block(block,versions,db_root=self.db.root_dir,db=self.db)
            self.inspector.show_block(block,versions)

    def open_next_production_task(self):
        if not self.db:
            return
        task = ProductionController(self.db).next_task()
        if not task:
            QMessageBox.information(self, "Production Complete", "No production tasks remain.")
            return
        if task.get("block_id"):
            self.select_block(task["block_id"])
        self.open_production_task(task)

    def open_production_task(self, task):
        if not self.db:
            return
        if task.get("type") == "assembly":
            self.workflow_open_assembly()
            return
        dlg = ProductionDialog(self, self.db, task, self.provider_box.currentText())
        dlg.exec()
        if dlg.result_changed:
            self.refresh_production_ui()

    def review_next(self):
        if not self.db: return
        nxt=self.db.next_recommended_block()
        if nxt: self.select_block(nxt["id"])
    def progress_callback(self,i,total,block_id,message=""):
        self.queue_panel.set_progress(i,total,block_id,message); QApplication.processEvents()



    def on_music_changed(self, block_id):
        """Refresh all production UI after Music Studio changes a block."""
        if not self.db:
            return
        self.refresh_production_ui()
        if block_id:
            self.select_block(block_id)

    def on_image_changed(self, block_id):
        """Refresh all production UI after Image Studio changes a block."""
        if not self.db:
            return
        self.refresh_production_ui()
        if block_id:
            self.select_block(block_id)


    def workflow_generate_voice(self, block_id):
        self.select_block(block_id)
        self.open_production_task({
            "type": "voice",
            "block_id": block_id,
            "scene": self.db.block_with_scene(block_id)["scene_title"],
            "action": "Generate / approve voice",
            "reason": "Voice is required before accurate timing.",
        })

    def workflow_open_image_studio(self, block_id):
        self.select_block(block_id)
        self.open_production_task({
            "type": "image",
            "block_id": block_id,
            "scene": self.db.block_with_scene(block_id)["scene_title"],
            "action": "Import / approve image",
            "reason": "Approved image is required for assembly.",
        })

    def workflow_open_music_studio(self, block_id):
        self.select_block(block_id)
        self.open_production_task({
            "type": "music",
            "block_id": block_id,
            "scene": self.db.block_with_scene(block_id)["scene_title"],
            "action": "Import / approve music",
            "reason": "Music/SFX is missing.",
        })

    def workflow_open_assembly(self):
        try:
            self.tabs.focus_widget(self.assembly_studio)
            self.assembly_studio.refresh()
        except Exception:
            pass

    def open_generate_voice_dialog(self):
        if not self.db or not self.selected_block_id:
            QMessageBox.warning(self, "No block selected", "Select a block first.")
            return
        dlg = GenerateVoiceDialog(self, self.db, self.selected_block_id, self.provider_box.currentText())
        if dlg.exec():
            self.assistant.append_log(f"Voice generation result for {self.selected_block_id}: {dlg.result_status}")
            self.refresh_production_ui()
            if dlg.result_path and dlg.result_path.lower().endswith((".wav", ".mp3", ".m4a")):
                try:
                    os.startfile(dlg.result_path)
                except Exception:
                    pass

    def estimate_cost(self):
        if not self.db: return
        info=self.current_cost_info()
        QMessageBox.information(self,"Cost Estimate",f"""Provider: {info['provider']}
Mode: {info['mode']}
Blocks: {info['blocks']}
Characters: {info['chars']}
Estimated cost: ${info['estimated_cost']:.4f}
Paid enabled: {info['paid_enabled']}
Max allowed: ${info['max_cost']:.2f}

Assistant cost: $0.00
""")
    def confirm_paid_if_needed(self):
        info=self.current_cost_info()
        if info["provider"]=="mock": return True
        if not info["allowed"]:
            QMessageBox.warning(self,"Paid generation blocked",f"""Generation blocked.

Estimated: ${info['estimated_cost']:.4f}
Paid enabled: {info['paid_enabled']}
Max budget: ${info['max_cost']:.2f}

Edit .env only when ready:
ALLOW_PAID_GENERATION=true
""")
            return False
        return QMessageBox.question(self,"Confirm Paid Generation",f"""This may spend money.

Provider: {info['provider']}
Estimated cost: ${info['estimated_cost']:.4f}

Continue?""") == QMessageBox.Yes
    def generate_voice(self):
        if not self.db or not self.confirm_paid_if_needed(): return
        provider=self.provider_box.currentText()
        try:
            generated=BuildPipeline(self.db,provider_name=provider,progress=self.progress_callback).generate_voice(self.mode_box.currentText())
            self.assistant.append_log(f"Generated {generated} voice block(s)."); self.refresh_all()
        except Exception as e: QMessageBox.warning(self,"Generation stopped",str(e))
    def build_episode(self):
        if not self.db or not self.confirm_paid_if_needed(): return
        provider=self.provider_box.currentText(); self.assistant.append_log("BUILD STARTED")
        try:
            steps=BuildPipeline(self.db,provider_name=provider,progress=self.progress_callback).build_episode(self.mode_box.currentText())
            for name,ok in steps: self.assistant.append_log(("✓ " if ok else "✕ ")+name)
            self.export_capcut(silent=True); self.assistant.append_log("✓ CapCut export complete"); self.assistant.append_log("BUILD FINISHED"); self.refresh_all()
        except Exception as e:
            self.assistant.append_log("BUILD STOPPED: "+str(e)); QMessageBox.warning(self,"Build stopped",str(e))
    def approve_latest(self):
        if not self.selected_block_id: return
        try: BuildPipeline(self.db,provider_name="mock").approve_latest(self.selected_block_id); self.assistant.append_log(f"Approved voice {self.selected_block_id}"); self.refresh_all()
        except Exception as e: QMessageBox.critical(self,"Approve failed",str(e))
    def mark_redo(self):
        if not self.selected_block_id: return
        reason,ok=QInputDialog.getText(self,"Redo","Reason:")
        if ok: self.service.set_block_status(self.selected_block_id,"redo",reason); self.refresh_all()
    def reject_block(self):
        if not self.selected_block_id: return
        reason,ok=QInputDialog.getText(self,"Reject","Reason:")
        if ok: self.service.set_block_status(self.selected_block_id,"rejected",reason); self.refresh_all()
    def save_block(self):
        if not self.selected_block_id: return
        d=self.workspace.get_edit_data(); self.service.save_block(self.selected_block_id,d["character_id"],d["voice_state_id"],d["scene_label"],d["text"],d["image_prompt"],d["music_cue"],d["notes"]); self.assistant.append_log(f"Saved {self.selected_block_id}"); self.refresh_all()
    def set_image_status(self,status):
        if not self.selected_block_id: return
        self.service.set_image_status(self.selected_block_id,status); self.assistant.append_log(f"Image {self.selected_block_id}: {status}"); self.refresh_all()
    def set_music_status(self,status):
        if not self.selected_block_id: return
        self.service.set_music_status(self.selected_block_id,status); self.assistant.append_log(f"Music {self.selected_block_id}: {status}"); self.refresh_all()
    def export_capcut(self,silent=False):
        if not self.db: return
        path=export_capcut_csv(self.db); self.exports_text.append(f"Exported: {path}")
        p=self.db.project()
        if p: self.db.execute("UPDATE project SET export_status='approved' WHERE id=?", (p["id"],))
        if not silent: QMessageBox.information(self,"Exported",f"CapCut CSV exported:\n{path}")
        self.refresh_all()
    def generate_single_block(self, block_id):
        """Generate voice for a single block from the workspace Generate button."""
        if not self.db or not self.confirm_paid_if_needed(): return
        provider = self.provider_box.currentText()
        try:
            from hps.pipeline.build import BuildPipeline
            BuildPipeline(self.db, provider_name=provider, progress=self.progress_callback).provider.synthesize(db=self.db, block_id=block_id)
            self.assistant.append_log(f"Generated voice for {block_id}")
            self.refresh_all()
        except Exception as e:
            self.assistant.append_log("GENERATE FAILED: " + str(e))
            QMessageBox.warning(self, "Generate failed", str(e))


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
        if not self.selected_block_id: return
        row=self.db.one("SELECT * FROM audio_versions WHERE block_id=? ORDER BY version DESC LIMIT 1",(self.selected_block_id,))
        if not row: QMessageBox.warning(self,"No audio","No audio version yet."); return
        os.startfile(str(self.db.root_dir/row["path"]))

if __name__=="__main__":
    app=QApplication(sys.argv); app.setStyleSheet(STYLE); win=StudioQt(); win.show(); sys.exit(app.exec())
