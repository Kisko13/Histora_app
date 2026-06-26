from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QProgressBar,QTableWidget,QTableWidgetItem
class QueuePanel(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        self.label=QLabel("Queue idle")
        self.progress=QProgressBar()
        self.table=QTableWidget(0,7)
        self.table.setHorizontalHeaderLabels(["Block","Scene","Character","Voice","Image","Music","Issue"])
        l.addWidget(self.label); l.addWidget(self.progress); l.addWidget(self.table,1)
    def populate(self,db):
        rows=db.blocks() if db else []
        self.table.setRowCount(len(rows))
        for i,b in enumerate(rows):
            vals=[b["id"],b["scene_title"],b["character_id"],b["status"],b["image_status"],b["music_status"],b["issue"]]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def set_progress(self,i,total,block_id,message=""):
        self.progress.setValue(int((i/total)*100) if total else 0)
        self.label.setText(message or f"Processing {block_id} ({i}/{total})")
