from pathlib import Path
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFileDialog, QMessageBox, QComboBox, QCheckBox
)

from hps.controllers.production_controller import ProductionController
from hps.pipeline.build import BuildPipeline


class ProductionDialog(QDialog):
    """
    Universal v22 production dialog.

    Modes:
    - voice: generate and approve latest voice
    - image: import and approve image
    - music: import and approve music
    - assembly: informs user to use Assembly Studio for now
    """

    def __init__(self, parent, db, task, provider="mock"):
        super().__init__(parent)
        self.db = db
        self.task = task
        self.provider = provider
        self.controller = ProductionController(db)
        self.result_changed = False
        self.last_path = None

        self.setWindowTitle("Produce Task")
        self.resize(900, 760)

        layout = QVBoxLayout(self)
        self.title = QLabel("Produce Task")
        self.title.setObjectName("PanelTitle")
        layout.addWidget(self.title)

        self.meta = QLabel("")
        self.meta.setWordWrap(True)
        layout.addWidget(self.meta)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("padding:8px;background:#242424;border:1px solid #444;")
        layout.addWidget(self.status)

        self.script_label = QLabel("Script / Notes")
        layout.addWidget(self.script_label)
        self.script = QTextEdit()
        self.script.setMinimumHeight(210)
        self.script.setReadOnly(True)
        layout.addWidget(self.script, 2)

        row = QHBoxLayout()
        self.provider_box = QComboBox()
        self.provider_box.addItems(["mock", "qwen"])
        self.provider_box.setCurrentText(provider)
        self.dry_run = QCheckBox("Dry run / no paid request")
        self.dry_run.setChecked(True)
        row.addWidget(QLabel("Provider"))
        row.addWidget(self.provider_box)
        row.addWidget(self.dry_run)
        row.addStretch()
        layout.addLayout(row)

        btns = QHBoxLayout()
        self.primary_btn = QPushButton("Start")
        self.approve_btn = QPushButton("Approve Latest")
        self.open_btn = QPushButton("Open Latest")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.primary_btn)
        btns.addWidget(self.approve_btn)
        btns.addWidget(self.open_btn)
        btns.addStretch()
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)

        layout.addWidget(QLabel("Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        layout.addWidget(self.log, 1)

        self.primary_btn.clicked.connect(self.start_task)
        self.approve_btn.clicked.connect(self.approve_latest)
        self.open_btn.clicked.connect(self.open_latest)
        self.close_btn.clicked.connect(self.accept)

        self.load_task()

    def block(self):
        bid = self.task.get("block_id")
        return self.db.block_with_scene(bid) if bid else None

    def load_task(self):
        typ = self.task.get("type")
        bid = self.task.get("block_id") or "Episode"
        block = self.block()

        self.title.setText(f"{typ.upper()} — {bid}")
        self.meta.setText(
            f"Scene: {self.task.get('scene','')}\n"
            f"Action: {self.task.get('action','')}\n"
            f"Reason: {self.task.get('reason','')}"
        )
        self.status.setText(f"Current task type: {typ}")

        if block:
            self.script.setPlainText(block["text"] or "")
        else:
            self.script.setPlainText("Episode-level task.")

        if typ == "voice":
            self.primary_btn.setText("Generate Voice")
            self.approve_btn.setText("Approve Latest Voice")
            self.provider_box.setEnabled(True)
        elif typ == "image":
            self.primary_btn.setText("Import Image")
            self.approve_btn.setText("Approve Imported Image")
            self.provider_box.setEnabled(False)
            self.dry_run.setVisible(False)
        elif typ == "music":
            self.primary_btn.setText("Import Music/SFX")
            self.approve_btn.setText("Approve Imported Audio")
            self.provider_box.setEnabled(False)
            self.dry_run.setVisible(False)
        elif typ == "assembly":
            self.primary_btn.setText("Open Assembly Studio")
            self.approve_btn.setEnabled(False)
            self.provider_box.setEnabled(False)
            self.dry_run.setVisible(False)

    def start_task(self):
        typ = self.task.get("type")
        bid = self.task.get("block_id")

        try:
            if typ == "voice":
                provider = self.provider_box.currentText()
                BuildPipeline(self.db, provider_name=provider).provider.synthesize(db=self.db, block_id=bid)
                self.result_changed = True
                self.log.append(f"Generated voice for {bid} using {provider}.")
                QMessageBox.information(self, "Voice Generated", f"Generated voice for {bid}. Review and approve latest.")

            elif typ == "image":
                file, _ = QFileDialog.getOpenFileName(self, "Import image", "", "Images (*.png *.jpg *.jpeg *.webp)")
                if file:
                    self.last_path = self.controller.import_image(bid, file)
                    self.result_changed = True
                    self.log.append(f"Imported image: {self.last_path}")
                    QMessageBox.information(self, "Imported", str(self.last_path))

            elif typ == "music":
                file, _ = QFileDialog.getOpenFileName(self, "Import music/SFX", "", "Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg)")
                if file:
                    self.last_path = self.controller.import_music(bid, file)
                    self.result_changed = True
                    self.log.append(f"Imported music/SFX: {self.last_path}")
                    QMessageBox.information(self, "Imported", str(self.last_path))

            elif typ == "assembly":
                self.result_changed = True
                self.accept()

        except Exception as exc:
            self.log.append("ERROR: " + str(exc))
            QMessageBox.warning(self, "Task failed", str(exc))

    def approve_latest(self):
        typ = self.task.get("type")
        bid = self.task.get("block_id")
        try:
            if typ == "voice":
                BuildPipeline(self.db, provider_name="mock").approve_latest(bid)
                self.result_changed = True
                self.log.append(f"Approved latest voice for {bid}.")
                QMessageBox.information(self, "Approved", f"Approved latest voice for {bid}.")

            elif typ == "image":
                if not self.last_path:
                    QMessageBox.warning(self, "No imported image", "Import an image first.")
                    return
                approved = self.controller.approve_image(bid, self.last_path)
                self.result_changed = True
                self.log.append(f"Approved image: {approved}")
                QMessageBox.information(self, "Approved", str(approved))

            elif typ == "music":
                if not self.last_path:
                    QMessageBox.warning(self, "No imported audio", "Import audio first.")
                    return
                approved = self.controller.approve_music(bid, self.last_path)
                self.result_changed = True
                self.log.append(f"Approved audio: {approved}")
                QMessageBox.information(self, "Approved", str(approved))

        except Exception as exc:
            self.log.append("ERROR: " + str(exc))
            QMessageBox.warning(self, "Approval failed", str(exc))

    def open_latest(self):
        if self.last_path and Path(self.last_path).exists():
            os.startfile(str(self.last_path))
        else:
            QMessageBox.information(self, "No latest file", "No file generated/imported in this dialog yet.")
