import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QTextEdit, QSplitter
)

from hps_qt.widgets.audio_player import AudioPlayer

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


class DropMusicLabel(QLabel):
    def __init__(self, owner):
        super().__init__("Drop music / SFX here or use Import Audio")
        self.owner = owner
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(220)
        self.setStyleSheet("border: 2px dashed #555; background:#101010; color:#aaa;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in AUDIO_EXTS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in AUDIO_EXTS:
                self.owner.import_audio(path)
                event.acceptProposedAction()
                return


class MusicStudioPanel(QWidget):
    music_changed = Signal(str)

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
        title = QLabel("Music Studio")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.block_label = QLabel("Current block: none")
        self.block_label.setWordWrap(True)
        layout.addWidget(self.block_label)

        buttons = QHBoxLayout()
        self.import_btn = QPushButton("Import Music/SFX")
        self.approve_btn = QPushButton("Approve Selected")
        self.reject_btn = QPushButton("Mark Rejected")
        self.open_folder_btn = QPushButton("Open Music Folder")
        self.open_file_btn = QPushButton("Open Selected")
        self.refresh_btn = QPushButton("Refresh")
        for b in [self.import_btn, self.approve_btn, self.reject_btn, self.open_file_btn, self.open_folder_btn, self.refresh_btn]:
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.drop_label = DropMusicLabel(self)
        self.player = AudioPlayer()
        left_layout.addWidget(self.drop_label)
        left_layout.addWidget(self.player)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Music / SFX Versions"))
        self.version_list = QListWidget()
        right_layout.addWidget(self.version_list, 2)
        right_layout.addWidget(QLabel("Notes / Cue"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Optional: mood, cue, volume, fade-in/out, scene usage...")
        right_layout.addWidget(self.notes, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
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
        self.block_id = block_id or ""
        self.block_label.setText(f"Current block: {self.block_id or 'none'}")
        self.refresh()

    def block_dir(self):
        if not self.db or not self.block_id:
            return None
        return self.db.root_dir / "assets" / "music" / self.block_id

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
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        file, _ = QFileDialog.getOpenFileName(self, "Import music/SFX", "", "Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg)")
        if file:
            self.import_audio(Path(file))

    def import_audio(self, src_path):
        if not self.db or not self.block_id:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        if not src_path.exists():
            QMessageBox.warning(self, "Missing file", str(src_path))
            return
        dst = self.next_version_path(src_path.suffix)
        shutil.copy2(src_path, dst)
        rel = str(dst.relative_to(self.db.root_dir)).replace("\\", "/")
        self.db.execute("UPDATE blocks SET music_status='generated' WHERE id=?", (self.block_id,))
        self.music_changed.emit(self.block_id)
        self.current_version_path = rel
        self.refresh(select_path=rel)
        QMessageBox.information(self, "Imported", f"Imported as:\n{dst}")

    def refresh(self, select_path=""):
        self.version_list.clear()
        self.current_version_path = ""
        if not self.db or not self.block_id:
            self.drop_label.setText("Select a block first")
            return

        d = self.block_dir()
        d.mkdir(parents=True, exist_ok=True)
        files = [p for p in sorted(d.glob("*")) if p.suffix.lower() in AUDIO_EXTS]

        approved = d / "approved.wav"
        approved_any = None
        for p in files:
            if p.name.startswith("approved."):
                approved_any = p
                break

        for p in files:
            rel = str(p.relative_to(self.db.root_dir)).replace("\\", "/")
            label = p.name
            if p.name.startswith("approved."):
                label = "✓ " + label
            elif approved_any and p.read_bytes() == approved_any.read_bytes():
                label = "✓ " + label
            item = QListWidgetItem(label)
            item.setData(1000, rel)
            self.version_list.addItem(item)
            if select_path and rel == select_path:
                self.version_list.setCurrentItem(item)

        if self.version_list.count() and not self.version_list.currentItem():
            self.version_list.setCurrentRow(self.version_list.count()-1)

        if not files:
            self.drop_label.setText("No music/SFX yet.\nDrop audio here or use Import Music/SFX.")
        else:
            self.drop_label.setText("Music/SFX imported.\nSelect a version and use Open Selected to preview.")

    def on_select_version(self, item):
        if not item:
            self.player.clear()
            return
        self.current_version_path = item.data(1000)
        if self.db and self.current_version_path:
            path = self.db.root_dir / self.current_version_path
            if path.exists():
                self.player.load(path)
            else:
                self.player.clear()

    def selected_path(self):
        item = self.version_list.currentItem()
        if not item or not self.db:
            return None
        return self.db.root_dir / item.data(1000)

    def approve_selected(self):
        path = self.selected_path()
        if not path or not path.exists():
            QMessageBox.warning(self, "No audio selected", "Select a music/SFX version first.")
            return
        approved = self.block_dir() / ("approved" + path.suffix.lower())
        shutil.copy2(path, approved)
        self.db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (self.block_id,))
        self.music_changed.emit(self.block_id)
        self.refresh(select_path=str(approved.relative_to(self.db.root_dir)).replace("\\", "/"))
        QMessageBox.information(self, "Approved", f"Approved music/SFX:\n{approved}")

    def reject_selected(self):
        path = self.selected_path()
        if not path:
            QMessageBox.warning(self, "No audio selected", "Select a music/SFX version first.")
            return
        if path.name.startswith("approved."):
            QMessageBox.warning(self, "Cannot reject approved copy", "Select a version file, not approved copy.")
            return
        rejected = path.with_name(path.stem + "_rejected" + path.suffix)
        path.rename(rejected)
        self.db.execute("UPDATE blocks SET music_status='redo' WHERE id=?", (self.block_id,))
        self.music_changed.emit(self.block_id)
        self.refresh()
        QMessageBox.information(self, "Rejected", f"Marked rejected:\n{rejected}")

    def open_folder(self):
        d = self.block_dir()
        if not d:
            QMessageBox.warning(self, "No block", "Select a block first.")
            return
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))

    def open_selected(self):
        path = self.selected_path()
        if not path or not path.exists():
            QMessageBox.warning(self, "No audio selected", "Select an audio file first.")
            return
        os.startfile(str(path))
