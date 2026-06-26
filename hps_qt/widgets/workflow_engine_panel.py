from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox
)

from hps.core.block_state import compute_project_state


class WorkflowEnginePanel(QWidget):
    """
    v20.1 production queue:
    - creates an explicit prioritized queue of tasks
    - voice tasks outrank image/music tasks
    - Do Next Task always executes row #1
    """
    jump_to_block = Signal(str)
    request_voice = Signal(str)
    request_image = Signal(str)
    request_music = Signal(str)
    request_assembly = Signal()

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        self.queue = []

        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(lambda _: self.refresh())

        layout = QVBoxLayout(self)
        title = QLabel("Production Queue")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.summary = QLabel("No project loaded")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.next_card = QLabel("Queue empty")
        self.next_card.setWordWrap(True)
        self.next_card.setStyleSheet("font-size:16px; padding:12px; background:#242424; border:1px solid #444;")
        layout.addWidget(self.next_card)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Queue")
        self.do_next_btn = QPushButton("Do Next Task")
        self.jump_btn = QPushButton("Jump To Selected Task")
        self.open_assembly_btn = QPushButton("Open Assembly")
        row.addWidget(self.refresh_btn)
        row.addWidget(self.do_next_btn)
        row.addWidget(self.jump_btn)
        row.addWidget(self.open_assembly_btn)
        row.addStretch()
        layout.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["#", "Priority", "Type", "Block", "Scene", "Action", "Reason"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 3)

        layout.addWidget(QLabel("Workflow Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(150)
        layout.addWidget(self.log, 1)

        self.refresh_btn.clicked.connect(self.refresh)
        self.do_next_btn.clicked.connect(self.do_next)
        self.jump_btn.clicked.connect(self.jump_selected)
        self.open_assembly_btn.clicked.connect(lambda: self.request_assembly.emit())

    def on_project_changed(self, db):
        self.db = db
        self.refresh()

    def build_queue(self):
        if not self.db:
            return []

        project = compute_project_state(self.db)
        tasks = []

        for s in project["states"]:
            block_id = s["block_id"]
            scene = s["scene"]

            # Priority rule:
            # Generate/approve voices first because image/music timing depends on voice length.
            if not s["voice_ok"]:
                tasks.append({
                    "priority": 100,
                    "type": "voice",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Generate / approve voice",
                    "reason": "Voice is required before accurate assembly timing.",
                })

            # Images are next: you need approved visuals for assembly.
            if s["voice_ok"] and not s["image_ok"]:
                tasks.append({
                    "priority": 80,
                    "type": "image",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Import / approve image",
                    "reason": "Approved image is required for assembly.",
                })

            # Music is lower than voice/image.
            # Music is allowed after voice exists, because you can judge timing/mood better.
            if s["voice_ok"] and s["image_ok"] and not s["music_ok"]:
                tasks.append({
                    "priority": 60,
                    "type": "music",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Import / approve music",
                    "reason": "Music is missing for this block.",
                })

        # If no asset tasks remain, move to assembly.
        if not tasks and project["assembly_ready"] == project["total"] and project["total"] > 0:
            tasks.append({
                "priority": 20,
                "type": "assembly",
                "block_id": "",
                "scene": "Episode",
                "action": "Refresh / export assembly manifest",
                "reason": "All blocks are assembly-ready.",
            })

        # Higher priority first. Within same priority, preserve block order.
        tasks.sort(key=lambda t: -t["priority"])
        return tasks

    def refresh(self):
        if not self.db:
            self.summary.setText("No project loaded")
            self.next_card.setText("Queue empty")
            self.table.setRowCount(0)
            return

        project = compute_project_state(self.db)
        total = project["total"]
        self.queue = self.build_queue()

        self.summary.setText(
            f"Complete {project['complete']}/{total} | "
            f"Assembly-ready {project['assembly_ready']}/{total} | "
            f"Voice {project['voice_done']}/{total} | "
            f"Images {project['image_done']}/{total} | "
            f"Music {project['music_done']}/{total} | "
            f"Queue tasks: {len(self.queue)}"
        )

        if self.queue:
            t = self.queue[0]
            self.next_card.setText(
                f"NEXT QUEUE ITEM\n\n"
                f"#{1} — {t['type'].upper()}\n"
                f"Block: {t['block_id'] or 'Episode'}\n"
                f"Scene: {t['scene']}\n"
                f"Action: {t['action']}\n"
                f"Reason: {t['reason']}"
            )
        else:
            self.next_card.setText("QUEUE COMPLETE\n\nNo production tasks remain.")

        self.table.setRowCount(len(self.queue))
        for i, t in enumerate(self.queue):
            vals = [
                str(i + 1),
                str(t["priority"]),
                t["type"],
                t["block_id"] or "Episode",
                t["scene"],
                t["action"],
                t["reason"],
            ]
            for c, v in enumerate(vals):
                self.table.setItem(i, c, QTableWidgetItem(v))

        self.log.append(f"Queue refreshed: {len(self.queue)} task(s).")

    def selected_task(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.queue):
            return self.queue[0] if self.queue else None
        return self.queue[row]

    def jump_selected(self):
        task = self.selected_task()
        if not task:
            QMessageBox.information(self, "Queue empty", "No task to jump to.")
            return
        if task["block_id"]:
            self.jump_to_block.emit(task["block_id"])
            self.log.append(f"Jumped to {task['block_id']}")
        else:
            self.request_assembly.emit()

    def do_next(self):
        task = self.queue[0] if self.queue else None
        if not task:
            QMessageBox.information(self, "Queue complete", "No tasks remain.")
            return

        block_id = task["block_id"]
        if block_id:
            self.jump_to_block.emit(block_id)

        if task["type"] == "voice":
            self.request_voice.emit(block_id)
        elif task["type"] == "image":
            self.request_image.emit(block_id)
        elif task["type"] == "music":
            self.request_music.emit(block_id)
        elif task["type"] == "assembly":
            self.request_assembly.emit()

        self.log.append(f"Started queue item: {task['type']} — {block_id or 'Episode'}")
