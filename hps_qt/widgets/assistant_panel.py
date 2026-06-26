from hps.core.block_state import compute_project_state
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QPushButton,QTextEdit
from PySide6.QtCore import Signal
class AssistantPanel(QWidget):
    build_clicked=Signal(); next_clicked=Signal(str)
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self)
        title=QLabel("Local Production Assistant"); title.setObjectName("PanelTitle")
        self.summary=QLabel("Open a project."); self.summary.setWordWrap(True)
        self.next_button=QPushButton("Next Task"); self.build_button=QPushButton("BUILD")
        self.log=QTextEdit(); self.log.setReadOnly(True)
        for w in [title,self.summary,self.next_button,self.build_button,self.log]: l.addWidget(w)
        l.setStretchFactor(self.log,1); self.build_button.clicked.connect(self.build_clicked.emit); self.next_block_id=None; self.next_button.clicked.connect(self._next)
    def _next(self):
        if self.next_block_id: self.next_clicked.emit(self.next_block_id)
    def refresh(self,db,cost_info=None):
        total=db.total_blocks(); approved=db.approved_count(); generated=db.generated_count(); missing=db.missing_count(); redo=db.redo_count(); nxt=db.next_recommended_block()
        self.next_block_id=nxt["id"] if nxt else None
        after = "Generate missing voices"
        if redo: after = "Regenerate redo blocks"
        elif generated: after = "Review generated voices"
        elif not missing: after = "Images → Music → Assembly → Export"
        cost_line=""
        if cost_info: cost_line=f"\nEstimated voice cost: ${cost_info['estimated_cost']:.4f}\nPaid enabled: {cost_info['paid_enabled']}"
        self.summary.setText(f"""Episode completion: {db.completion_percent()}%
Approved: {approved}/{total}
Generated awaiting review: {generated}
Redo: {redo}
Missing: {missing}{cost_line}

NEXT TASK
{self.next_block_id or "Production clear"}

TASK TYPE
{after}

AFTER THAT
Images → Music → Assembly → Export
""")
    def append_log(self,text): self.log.append(text)
