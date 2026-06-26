from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGridLayout

class MissionControl(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Mission Control")
        title.setObjectName("PanelTitle")
        self.overview = QLabel("")
        self.overview.setObjectName("Overview")
        self.overview.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.overview)

        grid = QGridLayout()
        layout.addLayout(grid)
        self.rows = {}
        for i, name in enumerate(["Story", "Voice", "Images", "Music", "Assembly", "Export"]):
            label = QLabel(name)
            bar = QProgressBar()
            val = QLabel("0%")
            grid.addWidget(label, i, 0)
            grid.addWidget(bar, i, 1)
            grid.addWidget(val, i, 2)
            self.rows[name.lower()] = (bar, val)

    def set_row(self, key, done, total):
        pct = int(done / max(1, total) * 100)
        bar, val = self.rows[key]
        bar.setValue(pct)
        val.setText(f"{done}/{total}" if total != 1 else f"{pct}%")

    def refresh(self, db):
        if not db:
            return
        p = db.project()
        runtime = db.runtime_seconds_estimate()
        self.overview.setText(
            f"Episode: {p['title'] if p else ''}\n"
            f"Scenes: {len(db.scenes())}   Blocks: {db.total_blocks()}   Characters: {len(db.characters())}   Voices: {len(db.voices())}\n"
            f"Estimated runtime: {runtime//60}m {runtime%60}s   Current estimated spend: ${db.total_estimated_spend():.4f}"
        )
        self.set_row("story", *db.story_progress())
        self.set_row("voice", *db.voice_progress())
        self.set_row("images", *db.image_progress())
        self.set_row("music", *db.music_progress())
        self.set_row("assembly", *db.assembly_progress())
        self.set_row("export", *db.export_progress())
