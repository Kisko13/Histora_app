from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """
    Central UI state for the whole application.

    Panels should not keep their own idea of the selected block.
    They subscribe to this object instead.
    """
    project_changed = Signal(object)
    selected_block_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.db = None
        self.selected_block_id = ""

    def set_project(self, db):
        self.db = db
        self.project_changed.emit(db)
        # Preserve selected block only if it still exists.
        if self.selected_block_id and db and db.block(self.selected_block_id):
            self.selected_block_changed.emit(self.selected_block_id)
        else:
            self.set_selected_block("")

    def set_selected_block(self, block_id):
        block_id = block_id or ""
        self.selected_block_id = block_id
        self.selected_block_changed.emit(block_id)

    def current_block(self):
        if not self.db or not self.selected_block_id:
            return None
        return self.db.block_with_scene(self.selected_block_id)
