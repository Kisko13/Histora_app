from PySide6.QtWidgets import QFrame,QVBoxLayout,QLabel
class StatCard(QFrame):
    def __init__(self,title,value="0"):
        super().__init__(); self.setObjectName("StatCard")
        l=QVBoxLayout(self)
        self.title=QLabel(title.upper()); self.title.setObjectName("CardTitle")
        self.value=QLabel(value); self.value.setObjectName("CardValue")
        l.addWidget(self.title); l.addWidget(self.value); l.setContentsMargins(14,10,14,10)
    def set_value(self,value): self.value.setText(str(value))
