from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QLineEdit, QFrame, QGridLayout,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Signal, Qt

from hps_qt.widgets.audio_player import AudioPlayer
from hps.core.block_state import compute_block_state


class Section(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("Section")
        self.layout = QVBoxLayout(self)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        self.layout.addWidget(label)


class InfoBadge(QFrame):
    def __init__(self, title, value="-"):
        super().__init__()
        self.setObjectName("InfoBadge")
        l = QVBoxLayout(self)
        self.t = QLabel(title.upper())
        self.t.setObjectName("BadgeTitle")
        self.v = QLabel(value)
        self.v.setObjectName("BadgeValue")
        l.addWidget(self.t)
        l.addWidget(self.v)

    def set_value(self, value):
        self.v.setText(str(value))


class BlockWorkspace(QWidget):
    generate_clicked = Signal()
    open_selected_version_clicked = Signal()
    approve_clicked = Signal()
    redo_clicked = Signal()
    reject_clicked = Signal()
    open_audio_clicked = Signal()   # kept for compatibility (opens externally)
    save_clicked = Signal()
    image_approve_clicked = Signal()
    image_redo_clicked = Signal()
    music_approve_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.current_block_id = None
        self._db_root = None         # set by load_block so player can resolve paths
        self._audio_versions = []

        l = QVBoxLayout(self)

        self.title = QLabel("Select a block")
        self.title.setObjectName("WorkspaceTitle")
        l.addWidget(self.title)
        self.generate_voice_button = QPushButton('⚡ Generate Voice')
        self.generate_voice_button.clicked.connect(self.generate_clicked.emit)
        l.addWidget(self.generate_voice_button)


        # ── status badges ────────────────────────────────────────────
        badges = QHBoxLayout()
        self.badges = {}
        for name in ["Character", "Delivery", "Voice", "Image", "Music", "Versions"]:
            b = InfoBadge(name)
            self.badges[name.lower()] = b
            badges.addWidget(b)
        l.addLayout(badges)

        # ── voice action buttons ──────────────────────────────────────
        row = QHBoxLayout()
        btn_generate = QPushButton("⚡ Generate Voice")
        btn_generate.clicked.connect(self._generate_for_block)
        btn_approve  = QPushButton("✓ Approve Voice")
        btn_approve.clicked.connect(self.approve_clicked.emit)
        btn_redo     = QPushButton("↻ Redo Voice")
        btn_redo.clicked.connect(self.redo_clicked.emit)
        btn_reject   = QPushButton("✕ Reject")
        btn_reject.clicked.connect(self.reject_clicked.emit)
        for b in [btn_generate, btn_approve, btn_redo, btn_reject]:
            row.addWidget(b)
        row.addStretch()
        l.addLayout(row)

        # ── embedded audio player ─────────────────────────────────────
        player_section = QFrame()
        player_section.setObjectName("Section")
        ps_layout = QVBoxLayout(player_section)
        player_label = QLabel("VOICE REVIEW — INLINE PLAYER")
        player_label.setObjectName("SectionTitle")
        ps_layout.addWidget(player_label)

        self.audio_player = AudioPlayer()
        ps_layout.addWidget(self.audio_player)

        # Version selector: clicking a version loads it into the player
        self.version_list = QListWidget()
        self.version_list.setMaximumHeight(90)
        self.version_list.itemClicked.connect(self._on_version_selected)
        ps_layout.addWidget(QLabel("Versions (click to load):"))
        ps_layout.addWidget(self.version_list)

        l.addWidget(player_section)

        # ── script + image + music + meta grid ───────────────────────
        grid = QGridLayout()
        l.addLayout(grid, 1)

        self.script_text  = QTextEdit()
        self.script_text.setPlaceholderText("Script text")
        self.image_prompt = QTextEdit()
        self.image_prompt.setPlaceholderText("Image prompt for this block/scene")
        self.music_cue    = QLineEdit()
        self.music_cue.setPlaceholderText("Music cue / mood / file name")
        self.notes        = QTextEdit()
        self.notes.setPlaceholderText("Production notes")
        self.character    = QComboBox()
        self.voice_state  = QComboBox()
        self.scene_label  = QLineEdit()
        self.save         = QPushButton("Save Block")
        self.image_approve = QPushButton("Approve Image")
        self.image_redo    = QPushButton("Mark Image Redo")
        self.music_approve = QPushButton("Approve Music Cue")

        script = Section("SCRIPT")
        script.layout.addWidget(self.script_text)

        image = Section("IMAGE")
        image.layout.addWidget(self.image_prompt)
        image.layout.addWidget(self.image_approve)
        image.layout.addWidget(self.image_redo)

        music = Section("MUSIC")
        music.layout.addWidget(self.music_cue)
        music.layout.addWidget(self.music_approve)

        meta = Section("METADATA")
        for lbl, w in [("Character", self.character), ("Voice State", self.voice_state), ("Scene Label", self.scene_label)]:
            meta.layout.addWidget(QLabel(lbl))
            meta.layout.addWidget(w)
        meta.layout.addWidget(self.save)
        meta.layout.addStretch()

        notes_sec = Section("NOTES")
        notes_sec.layout.addWidget(self.notes)

        grid.addWidget(script,    0, 0, 3, 1)
        grid.addWidget(meta,      0, 1)
        grid.addWidget(image,     0, 2)
        grid.addWidget(music,     1, 2)
        grid.addWidget(notes_sec, 3, 0, 1, 3)

        self.save.clicked.connect(self.save_clicked.emit)
        self.image_approve.clicked.connect(self.image_approve_clicked.emit)
        self.image_redo.clicked.connect(self.image_redo_clicked.emit)
        self.music_approve.clicked.connect(self.music_approve_clicked.emit)

    # ── signal: generate voice for this block only ───────────────────────────
    # This signal is caught by StudioQt and triggers a single-block generate
    generate_block_clicked = Signal(str)   # emits block_id

    def _generate_for_block(self):
        if self.current_block_id:
            self.generate_block_clicked.emit(self.current_block_id)

    # ── version list click ────────────────────────────────────────────────────
    def _on_version_selected(self, item):
        idx = self.version_list.row(item)
        if 0 <= idx < len(self._audio_versions) and self._db_root:
            v = self._audio_versions[idx]
            abs_path = Path(self._db_root) / v["path"]
            if abs_path.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac"):
                self.audio_player.load(abs_path)
            else:
                self.audio_player.clear()
                self.audio_player._status_label.setText(f"Non-audio: {abs_path.name}")

    # ── public API ────────────────────────────────────────────────────────────
    def set_dropdowns(self, characters, voice_states):
        self.character.clear()
        self.character.addItems(characters)
        self.voice_state.clear()
        self.voice_state.addItems(voice_states)

    def load_block(self, block, audio_versions, db_root=None, db=None):
        self._db_root = db_root or Path(".")
        self._db = db  # stored so compute_block_state can be called
        self._audio_versions = list(audio_versions)
        self.current_block_id = block["id"]
        self.title.setText(f"{block['id']} — {block['scene_title']}")
        self.badges["character"].set_value(block["character_id"])
        self.badges["delivery"].set_value(block["voice_state_id"])

        # Use block_state as single source of truth for all asset statuses
        if db is not None:
            try:
                state = compute_block_state(db, block["id"])
                self.badges["voice"].set_value("approved" if state["voice_ok"] else (block["status"] or "missing"))
                self.badges["image"].set_value("approved" if state["image_ok"] else (block["image_status"] or "missing"))
                self.badges["music"].set_value("approved" if state["music_ok"] else (block["music_status"] or "missing"))
            except Exception:
                self.badges["voice"].set_value(block["status"])
                self.badges["image"].set_value(block["image_status"] or "missing")
                self.badges["music"].set_value(block["music_status"] or "missing")
        else:
            self.badges["voice"].set_value(block["status"])
            self.badges["image"].set_value(block["image_status"] or "missing")
            self.badges["music"].set_value(block["music_status"] or "missing")
        self.badges["versions"].set_value(len(self._audio_versions))
        self.script_text.setPlainText(block["text"] or "")
        self.notes.setPlainText(block["notes"] or "")
        self.scene_label.setText(block["scene_label"] or "")
        self.character.setCurrentText(block["character_id"] or "")
        self.voice_state.setCurrentText(block["voice_state_id"] or "")
        self.image_prompt.setPlainText(block["image_prompt"] or "")
        self.music_cue.setText(block["music_cue"] or "")

        self.version_list.clear()
        for v in self._audio_versions:
            self.version_list.addItem(
                QListWidgetItem(
                    f"v{v['version']:03d}  [{v['status']}]  ${v['estimated_cost_usd']:.4f}  {v['path']}"
                )
            )

        # Auto-load latest audio version into player
        self.audio_player.clear()
        wav_versions = [v for v in self._audio_versions
                        if Path(v["path"]).suffix.lower() in (".wav", ".mp3", ".ogg", ".flac")]
        if wav_versions:
            latest = wav_versions[-1]
            abs_path = Path(self._db_root) / latest["path"]
            self.audio_player.load(abs_path)
            # highlight latest in list
            for i, v in enumerate(self._audio_versions):
                if v["path"] == latest["path"]:
                    self.version_list.setCurrentRow(i)

    def get_selected_version_path(self):
        item = self.version_list.currentItem()
        return item.data(1000) if item else ""

    def get_edit_data(self):
        return {
            "character_id":  self.character.currentText(),
            "voice_state_id": self.voice_state.currentText(),
            "scene_label":   self.scene_label.text(),
            "text":          self.script_text.toPlainText(),
            "image_prompt":  self.image_prompt.toPlainText(),
            "music_cue":     self.music_cue.text(),
            "notes":         self.notes.toPlainText(),
        }
