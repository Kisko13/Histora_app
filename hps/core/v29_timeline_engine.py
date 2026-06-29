from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hps.core.block_state import approved_voice_path
from hps.core.v29_asset_managers import VisualSlotManager, SceneMusicManager, project_dir


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _estimate_seconds(block) -> int:
    text = _get(block, "text", "") or ""
    return max(6, int(len(text.split()) / 2.15))


def _rel(root: Path, path: Path | None) -> str:
    if not path:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path)


class TimelineEngine:
    """Creates the canonical episode timeline consumed by the assembly engine."""

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.visuals = VisualSlotManager(db)
        self.music = SceneMusicManager(db)

    def build_timeline(self) -> dict:
        self.visuals.ensure_slot_folders()
        self.music.ensure_scene_folders()

        blocks = list(self.db.blocks())
        timeline_blocks = []
        current = 0

        for block in blocks:
            bid = _get(block, "id")
            duration = _estimate_seconds(block)
            slot = self.visuals.slot_for_block(bid) or {}
            scene_music = self.music.scene_for_block(bid) or {}
            voice = approved_voice_path(self.db, bid)
            visual_asset = self.visuals.find_approved_slot_asset(slot.get("id", "")) if slot else None
            music_asset = self.music.find_approved_scene_asset(scene_music.get("id", "")) if scene_music else None

            timeline_blocks.append({
                "block_id": bid,
                "scene_id": _get(block, "scene_id", ""),
                "scene_title": _get(block, "scene_title", ""),
                "character": _get(block, "character_id", _get(block, "character", "Narrator")),
                "start_seconds": current,
                "end_seconds": current + duration,
                "duration_seconds": duration,
                "voice_path": _rel(self.root, voice),
                "visual_slot_id": slot.get("id", ""),
                "visual_title": slot.get("title", ""),
                "visual_path": _rel(self.root, visual_asset),
                "scene_music_id": scene_music.get("id", ""),
                "scene_music_title": scene_music.get("title", ""),
                "scene_music_path": _rel(self.root, music_asset),
                "ready": bool(voice and visual_asset),
                "missing": [x for x, ok in {
                    "voice": bool(voice),
                    "visual_slot": bool(visual_asset),
                }.items() if not ok],
            })
            current += duration

        scene_rows = []
        for scene in self.db.scenes():
            sid = _get(scene, "id")
            scene_blocks = [b for b in timeline_blocks if b["scene_id"] == sid]
            if not scene_blocks:
                continue
            scene_rows.append({
                "scene_id": sid,
                "title": _get(scene, "title", sid),
                "start_seconds": scene_blocks[0]["start_seconds"],
                "end_seconds": scene_blocks[-1]["end_seconds"],
                "duration_seconds": scene_blocks[-1]["end_seconds"] - scene_blocks[0]["start_seconds"],
                "block_ids": [b["block_id"] for b in scene_blocks],
                "ready_blocks": sum(1 for b in scene_blocks if b["ready"]),
                "total_blocks": len(scene_blocks),
            })

        timeline = {
            "version": "v29_timeline",
            "policy": {
                "voice": "block_based",
                "visuals": "visual_slot_based",
                "music": "scene_based",
                "assembly": "timeline_driven_resume_safe",
            },
            "runtime_seconds": current,
            "runtime_minutes": round(current / 60, 2),
            "blocks": timeline_blocks,
            "scenes": scene_rows,
            "ready_blocks": sum(1 for b in timeline_blocks if b["ready"]),
            "total_blocks": len(timeline_blocks),
        }
        out = self.root / "production" / "timeline.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
        return timeline


def build_timeline(db) -> dict:
    return TimelineEngine(db).build_timeline()
