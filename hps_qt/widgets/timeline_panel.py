from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem
class TimelinePanel(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        l.addWidget(QLabel("Episode Timeline — local rough estimate"))
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["Start","End","Dur","Block","Scene","Character","Voice","Image"])
        l.addWidget(self.table,1)
    def populate(self,db):
        rows=db.timeline_rows() if db else []
        self.table.setRowCount(len(rows))
        def fmt(sec): return f"{sec//60:02d}:{sec%60:02d}"
        for i,row in enumerate(rows):
            b=row["block"]
            vals=[fmt(row["start"]),fmt(row["end"]),str(row["duration"])+"s",b["id"],b["scene_title"],b["character_id"],b["status"],b["image_status"]]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
