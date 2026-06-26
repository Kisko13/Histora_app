from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QPushButton
from PySide6.QtCore import Signal
class CostPanel(QWidget):
    estimate_clicked=Signal()
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        title=QLabel("Cost Control"); title.setObjectName("PanelTitle")
        self.info=QLabel("Mock mode is free. Paid generation disabled by default."); self.info.setWordWrap(True)
        self.estimate_button=QPushButton("Estimate Current Build Cost")
        l.addWidget(title); l.addWidget(self.info); l.addWidget(self.estimate_button); l.addStretch()
        self.estimate_button.clicked.connect(self.estimate_clicked.emit)
    def set_info(self,text): self.info.setText(text)
