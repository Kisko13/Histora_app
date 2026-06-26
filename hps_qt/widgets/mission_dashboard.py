from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton

from hps.core.block_state import compute_project_state


class MissionDashboard(QWidget):
    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(lambda _: self.refresh())

        layout = QVBoxLayout(self)
        title = QLabel("Mission Control")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.summary = QLabel("No project loaded")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.queue = QTextEdit()
        self.queue.setReadOnly(True)
        self.queue.setMinimumHeight(220)
        layout.addWidget(self.queue, 2)

        self.warnings = QTextEdit()
        self.warnings.setReadOnly(True)
        self.warnings.setMinimumHeight(160)
        layout.addWidget(QLabel("Warnings / Notes"))
        layout.addWidget(self.warnings, 1)

        self.refresh_btn = QPushButton("Refresh Dashboard")
        layout.addWidget(self.refresh_btn)
        self.refresh_btn.clicked.connect(self.refresh)

    def on_project_changed(self, db):
        self.db = db
        self.refresh()

    def build_queue_text(self, project):
        lines = []
        tasks = []
        for s in project["states"]:
            if not s["voice_ok"]:
                tasks.append(("🎤", "Voice", s["block_id"], s["scene"], "Generate / approve voice", 100))
            elif not s["image_ok"]:
                tasks.append(("🖼", "Image", s["block_id"], s["scene"], "Import / approve image", 80))
            elif not s["music_ok"]:
                tasks.append(("🎵", "Music", s["block_id"], s["scene"], "Import / approve music", 60))
        if not tasks and project["assembly_ready"] == project["total"] and project["total"] > 0:
            tasks.append(("🎬", "Assembly", "Episode", "Full episode", "Refresh/export assembly", 20))
        tasks.sort(key=lambda x: -x[5])
        for i, t in enumerate(tasks[:8], 1):
            icon, typ, bid, scene, action, _ = t
            lines.append(f"{i}. {icon} {typ} — {bid}")
            lines.append(f"   {action}")
            lines.append(f"   {scene}")
            lines.append("")
        return "\n".join(lines) if lines else "Queue complete."

    def refresh(self):
        if not self.db:
            self.summary.setText("No project loaded")
            self.queue.setPlainText("")
            self.warnings.setPlainText("")
            return
        project = compute_project_state(self.db)
        total = project["total"] or 1
        pct = int((project["complete"] / total) * 100)
        self.summary.setText(
            f"Episode completion: {pct}%\n"
            f"Complete: {project['complete']}/{project['total']}\n"
            f"Assembly-ready: {project['assembly_ready']}/{project['total']}\n"
            f"Voice: {project['voice_done']}/{project['total']}\n"
            f"Images: {project['image_done']}/{project['total']}\n"
            f"Music: {project['music_done']}/{project['total']}"
        )
        self.queue.setPlainText(self.build_queue_text(project))

        warns = []
        for s in project["states"]:
            if s["missing"]:
                warns.append(f"• {s['block_id']}: missing {', '.join(s['missing'])}")
        self.warnings.setPlainText("\n".join(warns) if warns else "No warnings.")
