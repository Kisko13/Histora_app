import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QTextEdit, QSplitter
)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class DropPreview(QLabel):
    def __init__(self, owner):
        super().__init__("Drop image here or use Import Image")
        self.owner = owner
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(420)
        self.setStyleSheet("border: 2px dashed #555; background:#101010; color:#aaa;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in IMAGE_EXTS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in IMAGE_EXTS:
                self.owner.import_image(path)
                event.acceptProposedAction()
                return


class ImageStudioPanel(QWidget):
    image_changed = Signal(str)
    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        self.block_id = None
        self.current_version_path = ""
        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(self.on_selected_block_changed)

        layout = QVBoxLayout(self)
        title = QLabel("Image Studio")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.block_label = QLabel("Current block: none")
        self.block_label.setWordWrap(True)
        layout.addWidget(self.block_label)

        buttons = QHBoxLayout()
        self.import_btn = QPushButton("Import Image")
        self.approve_btn = QPushButton("Approve Selected")
        self.reject_btn = QPushButton("Mark Rejected")
        self.open_folder_btn = QPushButton("Open Image Folder")
        self.open_file_btn = QPushButton("Open Selected")
        self.refresh_btn = QPushButton("Refresh")
        for b in [self.import_btn, self.approve_btn, self.reject_btn, self.open_file_btn, self.open_folder_btn, self.refresh_btn]:
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter()
        self.preview = DropPreview(self)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Image Versions"))
        self.version_list = QListWidget()
        right_layout.addWidget(self.version_list, 2)
        right_layout.addWidget(QLabel("Notes / Prompt"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Optional notes about this image, source, prompt, edits, continuity...")
        right_layout.addWidget(self.notes, 1)

        splitter.addWidget(self.preview)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.import_btn.clicked.connect(self.import_dialog)
        self.approve_btn.clicked.connect(self.approve_selected)
        self.reject_btn.clicked.connect(self.reject_selected)
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.open_file_btn.clicked.connect(self.open_selected)
        self.refresh_btn.clicked.connect(self.refresh)
        self.version_list.currentItemChanged.connect(self.on_select_version)

    def on_project_changed(self, db):
        self.db = db
        self.refresh()

    def on_selected_block_changed(self, block_id):
        self.block_id = block_id or ""
        self.block_label.setText(f"Current block: {self.block_id or 'none'}")
        self.refresh()

    def set_context(self, db, block_id):
        self.db = db
        self.block_id = block_id
        self.block_label.setText(f"Current block: {block_id or 'none'}")
        self.refresh()

    def block_dir(self):
        if not self.db or not self.block_id:
            return None
        return self.db.root_dir / "assets" / "images" / self.block_id

    def next_version_path(self, ext):
        d = self.block_dir()
        d.mkdir(parents=True, exist_ok=True)
        nums = []
        for p in d.glob("v*.*"):
            stem = p.stem.lower()
            if stem.startswith("v") and stem[1:].isdigit():
                nums.append(int(stem[1:]))
        n = max(nums) + 1 if nums else 1
        return d / f"v{n:03d}{ext.lower()}"

    def import_dialog(self):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first. If B001 is highlighted, click it once again or use Next Task.")
            return
        file, _ = QFileDialog.getOpenFileName(self, "Import image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file:
            self.import_image(Path(file))

    def import_image(self, src_path):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first. If B001 is highlighted, click it once again or use Next Task.")
            return
        if not src_path.exists():
            QMessageBox.warning(self, "Missing file", str(src_path))
            return
        dst = self.next_version_path(src_path.suffix)
        shutil.copy2(src_path, dst)
        rel = str(dst.relative_to(self.db.root_dir)).replace("\\", "/")
        self.db.execute("UPDATE blocks SET image_status='generated' WHERE id=?", (self.block_id,))
        self.image_changed.emit(self.block_id)
        self.current_version_path = rel
        self.refresh(select_path=rel)
        QMessageBox.information(self, "Imported", f"Imported as:\n{dst}")

    def refresh(self, select_path=""):
        self.version_list.clear()
        self.current_version_path = ""
        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(self.on_selected_block_changed)
        if not self.db or not self.block_id:
            self.preview.setText("Select a block first")
            self.preview.setPixmap(QPixmap())
            return

        d = self.block_dir()
        d.mkdir(parents=True, exist_ok=True)

        files = []
        for p in sorted(d.glob("*")):
            if p.suffix.lower() in IMAGE_EXTS:
                files.append(p)

        approved = d / "approved.png"
        for p in files:
            rel = str(p.relative_to(self.db.root_dir)).replace("\\", "/")
            label = p.name
            if p.name == "approved.png":
                label = "✓ approved.png"
            elif approved.exists() and p.read_bytes() == approved.read_bytes():
                label = "✓ " + label
            item = QListWidgetItem(label)
            item.setData(1000, rel)
            self.version_list.addItem(item)
            if select_path and rel == select_path:
                self.version_list.setCurrentItem(item)

        if self.version_list.count() and not self.version_list.currentItem():
            self.version_list.setCurrentRow(self.version_list.count()-1)

        if not files:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("No images yet.\nDrop image here or use Import Image.")

    def on_select_version(self, item):
        if not item or not self.db:
            return
        rel = item.data(1000)
        self.current_version_path = rel
        path = self.db.root_dir / rel
        self.load_preview(path)

    def load_preview(self, path):
        if not path.exists():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Image missing")
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText(f"Cannot preview:\n{path}")
            return
        scaled = pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_version_path and self.db:
            self.load_preview(self.db.root_dir / self.current_version_path)

    def selected_path(self):
        item = self.version_list.currentItem()
        if not item or not self.db:
            return None
        return self.db.root_dir / item.data(1000)

    def approve_selected(self):
        path = self.selected_path()
        if not path or not path.exists():
            QMessageBox.warning(self, "No image selected", "Select an image version first.")
            return
        approved = self.block_dir() / "approved.png"
        shutil.copy2(path, approved)
        self.db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (self.block_id,))
        self.image_changed.emit(self.block_id)
        self.refresh(select_path=str(approved.relative_to(self.db.root_dir)).replace("\\", "/"))
        QMessageBox.information(self, "Approved", f"Approved image:\n{approved}")

    def reject_selected(self):
        path = self.selected_path()
        if not path:
            QMessageBox.warning(self, "No image selected", "Select an image version first.")
            return
        rejected = path.with_name(path.stem + "_rejected" + path.suffix)
        if path.name == "approved.png":
            QMessageBox.warning(self, "Cannot reject approved copy", "Select a version image, not approved.png.")
            return
        path.rename(rejected)
        self.db.execute("UPDATE blocks SET image_status='redo' WHERE id=?", (self.block_id,))
        self.image_changed.emit(self.block_id)
        self.refresh()
        QMessageBox.information(self, "Rejected", f"Marked rejected:\n{rejected}")

    def open_folder(self):
        d = self.block_dir()
        if not d:
            QMessageBox.warning(self, "No block", "Select a block first. If B001 is highlighted, click it once again or use Next Task.")
            return
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))

    def open_selected(self):
        path = self.selected_path()
        if not path or not path.exists():
            QMessageBox.warning(self, "No image selected", "Select an image first.")
            return
        os.startfile(str(path))
