from pathlib import Path

ROOT = Path(__file__).resolve().parent

batch = ROOT / "hps" / "core" / "batch_production.py"
batch.write_text(r'''
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hps.core.production_queues import (
    ensure_character_library,
    generate_missing_voices,
    generate_missing_images,
    generate_missing_music,
)


def _project_dir(db) -> Path:
    return Path(str(db.path)).parent


def _write_report(db, report: dict) -> Path:
    out_dir = _project_dir(db) / "production"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "batch_report_latest.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _count_status(db):
    blocks = db.blocks()
    total = len(blocks)

    def count(field):
        n = 0
        for b in blocks:
            try:
                if b[field] == "generated":
                    n += 1
            except Exception:
                pass
        return n

    return {
        "total_blocks": total,
        "voice_generated": count("voice_status"),
        "image_generated": count("image_status"),
        "music_generated": count("music_status"),
    }


def run_batch_production(db, provider="mock", generate_voice=True, generate_images=True, generate_music=True, limit=None):
    started = datetime.now().isoformat(timespec="seconds")

    ensure_character_library(db)

    report = {
        "started": started,
        "provider": provider,
        "limit": limit,
        "steps": [],
        "before": _count_status(db),
    }

    if generate_voice:
        voices = generate_missing_voices(db, provider=provider, limit=limit)
        report["steps"].append({
            "step": "voices",
            "generated": len(voices),
            "items": voices,
        })

    if generate_images:
        images = generate_missing_images(db, limit=limit)
        report["steps"].append({
            "step": "images",
            "generated": len(images),
            "items": images,
        })

    if generate_music:
        music = generate_missing_music(db, limit=limit)
        report["steps"].append({
            "step": "music",
            "generated": len(music),
            "items": music,
        })

    report["after"] = _count_status(db)
    report["finished"] = datetime.now().isoformat(timespec="seconds")

    report_path = _write_report(db, report)
    report["report_path"] = str(report_path)
    return report
''', encoding="utf-8")


studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

if "from hps.core.batch_production import run_batch_production" not in s:
    s = s.replace(
        "from hps.core.production_queues import ensure_character_library, generate_missing_voices, generate_missing_images, generate_missing_music\n",
        "from hps.core.production_queues import ensure_character_library, generate_missing_voices, generate_missing_images, generate_missing_music\n"
        "from hps.core.batch_production import run_batch_production\n"
    )

if "def v27_generate_missing_assets" not in s:
    insert_at = s.find("    def v27_character_library(self):")
    methods = r'''
    def v27_generate_missing_assets(self):
        if not self.db:
            return

        from PySide6.QtWidgets import QInputDialog

        limit, ok = QInputDialog.getInt(
            self,
            "Batch Production",
            "How many missing blocks to generate per asset type?\nUse 0 for ALL.\nFor testing use 3, 5, or 10.",
            5,
            0,
            100000,
            1,
        )

        if not ok:
            return

        provider = self.provider_box.currentText() if hasattr(self, "provider_box") else "mock"
        real_limit = None if limit == 0 else limit

        try:
            report = run_batch_production(
                self.db,
                provider=provider,
                generate_voice=True,
                generate_images=True,
                generate_music=True,
                limit=real_limit,
            )

            msg = []
            for step in report["steps"]:
                msg.append(f"{step['step']}: {step['generated']}")

            QMessageBox.information(
                self,
                "Batch Production Complete",
                "Generated:\n"
                + "\n".join(msg)
                + f"\n\nReport:\n{report['report_path']}"
            )

            self.refresh_all()
            if self.selected_block_id:
                self.select_block(self.selected_block_id)

        except Exception as exc:
            QMessageBox.critical(self, "Batch Production Failed", str(exc))

'''
    s = s[:insert_at] + methods + s[insert_at:]

if "Generate Missing Assets" not in s:
    s = s.replace(
        '        self.music_queue_btn = QPushButton("Generate Missing Music")',
        '        self.music_queue_btn = QPushButton("Generate Missing Music")\n'
        '        self.batch_assets_btn = QPushButton("Generate Missing Assets")'
    )

    s = s.replace(
        '        toolbar.addWidget(self.music_queue_btn)',
        '        toolbar.addWidget(self.music_queue_btn)\n'
        '        toolbar.addWidget(self.batch_assets_btn)'
    )

    s = s.replace(
        '        self.music_queue_btn.clicked.connect(self.v27_generate_missing_music)',
        '        self.music_queue_btn.clicked.connect(self.v27_generate_missing_music)\n'
        '        self.batch_assets_btn.clicked.connect(self.v27_generate_missing_assets)'
    )

studio.write_text(s, encoding="utf-8")


dashboard = ROOT / "hps" / "core" / "production_dashboard.py"
dashboard.write_text(r'''
from __future__ import annotations

import json
from pathlib import Path


def production_dashboard_report(db) -> dict:
    blocks = db.blocks()
    total = len(blocks)

    def status_count(field, value):
        n = 0
        for b in blocks:
            try:
                if b[field] == value:
                    n += 1
            except Exception:
                pass
        return n

    voice = status_count("voice_status", "generated")
    image = status_count("image_status", "generated")
    music = status_count("music_status", "generated")

    return {
        "project": str(db.path),
        "total_blocks": total,
        "voice": {
            "generated": voice,
            "missing": max(0, total - voice),
            "percent": round((voice / total) * 100, 1) if total else 0,
        },
        "images": {
            "generated": image,
            "missing": max(0, total - image),
            "percent": round((image / total) * 100, 1) if total else 0,
        },
        "music": {
            "generated": music,
            "missing": max(0, total - music),
            "percent": round((music / total) * 100, 1) if total else 0,
        },
    }


def save_dashboard_report(db) -> Path:
    path = Path(str(db.path)).parent / "production" / "dashboard_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(production_dashboard_report(db), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
''', encoding="utf-8")


doc = ROOT / "docs" / "V27_BATCH_PRODUCTION_CONTROL.md"
doc.write_text("""# V27 Batch Production Control

Adds:

- Generate Missing Assets
- test limit prompt: 0 = all, 5 = first 5 missing per type
- runs voice/image/music queues together
- saves `production/batch_report_latest.json`
- keeps mock/offline workflow free except future real voice providers

Test recommendation:

1. Set provider to mock.
2. Click Generate Missing Assets.
3. Enter 5.
4. Confirm 5 voices, 5 images, 5 music placeholders generated.
5. Check production/batch_report_latest.json.
""", encoding="utf-8")

print("V27 batch production control installed.")
print("Run: .\\run_studio_v24.bat")