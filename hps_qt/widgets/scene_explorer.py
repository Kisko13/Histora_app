from hps.core.block_state import compute_block_state
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Signal
class SceneExplorer(QTreeWidget):
    block_selected=Signal(str); scene_selected=Signal(str)
    def __init__(self):
        super().__init__(); self.setHeaderHidden(True); self.itemSelectionChanged.connect(self._on_select)
    def populate(self,db):
        self.clear()
        if not db: return
        blocks=db.blocks()
        for scene in db.scenes():
            item=QTreeWidgetItem([f"▼ {scene['id']}  {scene['title']}"])
            item.setData(0,1000,("scene",scene["id"]))
            self.addTopLevelItem(item)
            for b in [x for x in blocks if x["scene_id"]==scene["id"]]:
                state = compute_block_state(db, b["id"])
                icon = state["icon"]
                img = "🖼✓" if state["image_ok"] else "🖼·"
                mus = "🎵✓" if state["music_ok"] else "🎵·"
                voice = "🎤✓" if state["voice_ok"] else "🎤·"
                child=QTreeWidgetItem([f"{icon} {b['id']}  {b['character_id']}  {voice} {img} {mus}"])
                child.setData(0,1000,("block",b["id"]))
                item.addChild(child)
            item.setExpanded(True)
    def _on_select(self):
        items=self.selectedItems()
        if not items: return
        typ,ident=items[0].data(0,1000)
        self.block_selected.emit(ident) if typ=="block" else self.scene_selected.emit(ident)
