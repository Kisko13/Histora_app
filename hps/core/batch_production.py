
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
