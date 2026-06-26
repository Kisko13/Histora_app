import csv
import json
import os
import wave
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QTextEdit
)


def wav_duration_seconds(path: Path):
    try:
        if path.suffix.lower() != ".wav":
            return None
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate:
                return frames / float(rate)
    except Exception:
        return None
    return None


class AssemblyStudioPanel(QWidget):
    """
    First assembly milestone:
    - Reads approved block assets.
    - Shows readiness per block.
    - Exports assembly manifest JSON + CSV.
    - Does not render MP4 yet.
    """

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.db = None
        if self.state is not None:
            self.state.project_changed.connect(self.on_project_changed)
            self.state.selected_block_changed.connect(lambda _: self.refresh())

        layout = QVBoxLayout(self)

        title = QLabel("Assembly Studio")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.summary = QLabel("No project loaded")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Assembly")
        self.export_manifest_btn = QPushButton("Export Manifest")
        self.open_export_btn = QPushButton("Open Assembly Folder")
        row.addWidget(self.refresh_btn)
        row.addWidget(self.export_manifest_btn)
        row.addWidget(self.open_export_btn)
        row.addStretch()
        layout.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Block", "Scene", "Voice", "Image", "Music", "Ready", "Duration", "Notes"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 3)

        layout.addWidget(QLabel("Assembly Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        layout.addWidget(self.log, 1)

        self.refresh_btn.clicked.connect(self.refresh)
        self.export_manifest_btn.clicked.connect(self.export_manifest)
        self.open_export_btn.clicked.connect(self.open_assembly_folder)

    def on_project_changed(self, db):
        self.db = db
        self.refresh()

    def assembly_dir(self):
        if not self.db:
            return None
        return self.db.root_dir / "exports" / "assembly"

    def latest_approved_voice(self, block_id):
        if not self.db:
            return None
        rows = self.db.query(
            "SELECT * FROM audio_versions WHERE block_id=? AND status='approved' ORDER BY version DESC",
            (block_id,)
        )
        if rows:
            return self.db.root_dir / rows[0]["path"]
        # fallback final folder
        final_dir = self.db.root_dir / "assets" / "audio_final"
        for ext in [".wav", ".mp3", ".m4a", ".txt", ""]:
            p = final_dir / f"{block_id}{ext}"
            if p.exists():
                return p
        return None

    def approved_image(self, block_id):
        d = self.db.root_dir / "assets" / "images" / block_id
        if not d.exists():
            return None
        for name in ["approved.png", "approved.jpg", "approved.jpeg", "approved.webp"]:
            p = d / name
            if p.exists():
                return p
        return None

    def approved_music(self, block_id):
        d = self.db.root_dir / "assets" / "music" / block_id
        if not d.exists():
            return None
        for p in d.iterdir():
            if p.is_file() and p.name.startswith("approved."):
                return p
        return None

    def build_rows(self):
        if not self.db:
            return []
        rows = []
        for b in self.db.blocks():
            block_id = b["id"]
            block = self.db.block_with_scene(block_id)
            voice = self.latest_approved_voice(block_id)
            image = self.approved_image(block_id)
            music = self.approved_music(block_id)

            voice_ok = bool(voice and voice.exists())
            image_ok = bool(image and image.exists())
            music_ok = bool(music and music.exists())

            duration = wav_duration_seconds(voice) if voice_ok else None
            if duration is None:
                # fallback estimate from chars: roughly 13 chars/sec for slow narration
                txt = block["text"] or ""
                duration = max(3.0, len(txt) / 13.0) if txt else 0.0

            ready = voice_ok and image_ok
            # Music can be optional later, but for now count it in notes, not hard readiness.
            notes = []
            if not voice_ok: notes.append("missing approved voice")
            if not image_ok: notes.append("missing approved image")
            if not music_ok: notes.append("music missing/optional")

            rows.append({
                "block_id": block_id,
                "scene": block["scene_title"],
                "character": block["character_id"],
                "voice": str(voice.relative_to(self.db.root_dir)).replace("\\", "/") if voice_ok else "",
                "image": str(image.relative_to(self.db.root_dir)).replace("\\", "/") if image_ok else "",
                "music": str(music.relative_to(self.db.root_dir)).replace("\\", "/") if music_ok else "",
                "ready": ready,
                "duration_seconds": round(duration, 2),
                "notes": "; ".join(notes),
                "text": block["text"] or "",
            })
        return rows

    def refresh(self):
        rows = self.build_rows()
        self.table.setRowCount(len(rows))

        ready_count = sum(1 for r in rows if r["ready"])
        total = len(rows)
        duration = sum(r["duration_seconds"] for r in rows)

        self.summary.setText(
            f"Assembly readiness: {ready_count}/{total} blocks ready | "
            f"Estimated runtime: {int(duration//60)}m {int(duration%60)}s | "
            "Ready requires approved voice + approved image. Music is tracked but optional for now."
        )

        for i, r in enumerate(rows):
            vals = [
                r["block_id"],
                r["scene"],
                "✓" if r["voice"] else "missing",
                "✓" if r["image"] else "missing",
                "✓" if r["music"] else "optional/missing",
                "READY" if r["ready"] else "NOT READY",
                f"{r['duration_seconds']:.1f}s",
                r["notes"],
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c in [2,3,4,5]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, c, item)

        self.log.append(f"Refreshed assembly: {ready_count}/{total} ready.")

    def export_manifest(self):
        if not self.db:
            QMessageBox.warning(self, "No project", "Open a project first.")
            return
        rows = self.build_rows()
        d = self.assembly_dir()
        d.mkdir(parents=True, exist_ok=True)

        manifest = {
            "project": self.db.project()["id"] if self.db.project() else "",
            "title": self.db.project()["title"] if self.db.project() else "",
            "blocks": rows,
            "notes": "Generated by Historical POV Studio v18 Assembly Studio. This is a manifest, not final MP4.",
        }

        json_path = d / "assembly_manifest.json"
        csv_path = d / "assembly_manifest.csv"

        json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "block_id", "scene", "character", "voice", "image", "music", "ready", "duration_seconds", "notes"
            ])
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r[k] for k in writer.fieldnames})

        QMessageBox.information(self, "Manifest Exported", f"Exported:\n{json_path}\n{csv_path}")
        self.log.append(f"Exported assembly manifest: {json_path}")

    def open_assembly_folder(self):
        d = self.assembly_dir()
        if not d:
            QMessageBox.warning(self, "No project", "Open a project first.")
            return
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))
