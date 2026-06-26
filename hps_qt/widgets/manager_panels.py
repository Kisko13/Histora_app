from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem
class CharacterManager(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        l.addWidget(QLabel("Character Manager"))
        self.table=QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(["Character","Role","Voice","Baseline"])
        l.addWidget(self.table,1)
    def populate(self,db):
        rows=db.characters() if db else []
        self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r["id"],r["role"],r["actor_voice_id"],r["baseline"]]): self.table.setItem(i,j,QTableWidgetItem(str(v)))
class ImageManager(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        l.addWidget(QLabel("Image Manager — local planning only, no paid image API"))
        self.table=QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(["Block","Scene","Status","Prompt"])
        l.addWidget(self.table,1)
    def populate(self,db):
        rows=db.blocks() if db else []
        self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r["id"],r["scene_title"],r["image_status"],r["image_prompt"]]): self.table.setItem(i,j,QTableWidgetItem(str(v)))
