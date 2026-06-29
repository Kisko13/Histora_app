from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hps.core.production_queues import ensure_character_library, generate_missing_voices
from hps.core.visual_slot_plan import generate_mock_visual_slots, create_visual_slot_plan
from hps.core.scene_music_plan import generate_mock_scene_music, create_scene_music_plan


def _project_dir(db) -> Path:
    return Path(str(db.path)).parent


def _write_report(db, report: dict) -> Path:
    out_dir = _project_dir(db) / "production"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "batch_report_latest.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _count_status(db):
    blocks = list(db.blocks())
    total = len(blocks)

    def generated_by_file(kind: str) -> int:
        if kind == "voice":
            from hps.core.block_state import approved_voice_path as path_fn
        elif kind == "image":
            from hps.core.block_state import approved_image_path as path_fn
        else:
            from hps.core.block_state import approved_music_path as path_fn
        return sum(1 for b in blocks if path_fn(db, b["id"]))

    visual_plan = _project_dir(db) / "production" / "visual_slot_plan.json"
    music_plan = _project_dir(db) / "production" / "scene_music_plan.json"

    return {
        "total_blocks": total,
        "voice_generated": generated_by_file("voice"),
        "image_blocks_covered": generated_by_file("image"),
        "music_blocks_covered": generated_by_file("music"),
        "visual_slot_plan_exists": visual_plan.exists(),
        "scene_music_plan_exists": music_plan.exists(),
    }


def plan_v28_media(db, visual_slots: int = 15) -> dict:
    """Plan visuals/music without generating voice."""
    ensure_character_library(db)
    visual = create_visual_slot_plan(db, slot_count=visual_slots)
    music = create_scene_music_plan(db)
    report = {
        "started": datetime.now().isoformat(timespec="seconds"),
        "mode": "plan_only",
        "visual_slots": visual.get("actual_slot_count", 0),
        "scene_music": music.get("scene_count", 0),
        "visual_plan": str(_project_dir(db) / "production" / "visual_slot_plan.json"),
        "music_plan": str(_project_dir(db) / "production" / "scene_music_plan.json"),
        "after": _count_status(db),
    }
    path = _write_report(db, report)
    report["report_path"] = str(path)
    return report


def run_batch_production(
    db,
    provider="mock",
    generate_voice=True,
    generate_images=True,
    generate_music=True,
    limit=None,
    progress=None,
    visual_slots: int = 15,
):
    """
    V28 production model:
    - voices are block-based
    - images are visual-slot based, default 15 across the whole video
    - music is scene-based, not per block
    """
    ensure_character_library(db)
    report = {
        "started": datetime.now().isoformat(timespec="seconds"),
        "version": "v28_visual_slots_scene_music",
        "provider": provider,
        "voice_limit": limit,
        "visual_slots_requested": visual_slots,
        "steps": [],
        "before": _count_status(db),
        "policy": {
            "voice": "block_based",
            "images": "visual_slot_based_not_per_block",
            "music": "scene_based_not_per_block",
            "paid_ai": "voice_only_when_provider_not_mock",
        },
    }

    if generate_voice:
        voices = generate_missing_voices(db, provider=provider, limit=limit, progress=progress)
        report["steps"].append({"step": "voices", "generated": len(voices), "items": voices})

    if generate_images:
        visual_plan = generate_mock_visual_slots(db, slot_count=visual_slots, progress=progress)
        report["steps"].append({
            "step": "visual_slots",
            "generated": visual_plan.get("generated_count", visual_plan.get("actual_slot_count", 0)),
            "items": visual_plan.get("slots", []),
        })

    if generate_music:
        music_plan = generate_mock_scene_music(db, progress=progress)
        report["steps"].append({
            "step": "scene_music",
            "generated": music_plan.get("generated_count", music_plan.get("scene_count", 0)),
            "items": music_plan.get("scenes", []),
        })

    report["after"] = _count_status(db)
    report["finished"] = datetime.now().isoformat(timespec="seconds")
    path = _write_report(db, report)
    report["report_path"] = str(path)
    return report
