from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QHBoxLayout

from hps.core.block_state import compute_project_state


class BlockStatePanel(QWidget):
    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None

        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(lambda _: self.refresh())

        layout = QVBoxLayout(self)
        title = QLabel("Block State Engine")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.summary = QLabel("No project loaded")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh State")
        row.addWidget(self.refresh_btn)
        row.addStretch()
        layout.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Block", "Scene", "Status", "Story", "Voice", "Image", "Music", "Assembly", "Next Task", "Missing"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 3)

        layout.addWidget(QLabel("State Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(130)
        layout.addWidget(self.log, 1)

        self.refresh_btn.clicked.connect(self.refresh)

    def on_project_changed(self, db):
        self.db = db
        self.refresh()

    def yesno(self, ok):
        return "✓" if ok else "—"

    def refresh(self):
        if not self.db:
            self.summary.setText("No project loaded")
            self.table.setRowCount(0)
            return

        project = compute_project_state(self.db)
        total = project["total"]
        self.summary.setText(
            f"Blocks complete: {project['complete']}/{total} | "
            f"Assembly-ready: {project['assembly_ready']}/{total} | "
            f"Voice: {project['voice_done']}/{total} | "
            f"Images: {project['image_done']}/{total} | "
            f"Music: {project['music_done']}/{total}"
        )

        states = project["states"]
        self.table.setRowCount(len(states))
        for r, s in enumerate(states):
            vals = [
                s["block_id"],
                s["scene"],
                f"{s['icon']} {s['status_label']}",
                self.yesno(s["story_ok"]),
                self.yesno(s["voice_ok"]),
                self.yesno(s["image_ok"]),
                self.yesno(s["music_ok"]),
                self.yesno(s["assembly_ready"]),
                s["next_task"],
                ", ".join(s["missing"]),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c in [3,4,5,6,7]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

        nxt = project["next"]
        if nxt:
            self.log.append(f"Next: {nxt['block_id']} — {nxt['next_task']} — missing: {', '.join(nxt['missing'])}")
        else:
            self.log.append("All blocks complete.")
