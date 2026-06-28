
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
