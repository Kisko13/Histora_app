from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGridLayout

class HealthDashboard(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('Project Health')
        title.setObjectName('PanelTitle')
        layout.addWidget(title)
        grid = QGridLayout()
        layout.addLayout(grid)
        self.rows = {}
        for i, name in enumerate(['Script', 'Voices', 'Images', 'Music', 'Thumbnail', 'Description', 'Export']):
            label = QLabel(name)
            bar = QProgressBar()
            value = QLabel('0%')
            grid.addWidget(label, i, 0)
            grid.addWidget(bar, i, 1)
            grid.addWidget(value, i, 2)
            self.rows[name.lower()] = (bar, value)

    def set_row(self, key, pct, text=None):
        bar, value = self.rows[key]
        bar.setValue(int(pct))
        value.setText(text or f'{int(pct)}%')

    def refresh(self, db):
        if not db:
            return
        p = db.project()
        total = max(1, db.total_blocks())
        voice_done, voice_total = db.voice_progress()
        image_done, image_total = db.image_progress()
        self.set_row('script', 100, 'Ready')
        self.set_row('voices', (voice_done / max(1, voice_total)) * 100, f'{voice_done}/{voice_total}')
        self.set_row('images', (image_done / max(1, image_total)) * 100, f'{image_done}/{image_total}')
        self.set_row('music', 0, p['music_status'] if p else 'missing')
        self.set_row('thumbnail', 100 if p and p['thumbnail_status'] == 'approved' else 0, p['thumbnail_status'] if p else 'missing')
        self.set_row('description', 100 if p and p['description_status'] == 'approved' else 0, p['description_status'] if p else 'missing')
        self.set_row('export', 100 if p and p['export_status'] == 'approved' else 0, p['export_status'] if p else 'missing')
