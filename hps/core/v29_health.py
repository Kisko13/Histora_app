from __future__ import annotations

import json
from pathlib import Path

from hps.core.block_state import approved_voice_path
from hps.core.v29_asset_managers import VisualSlotManager, SceneMusicManager, project_dir


def _pct(done: int, total: int) -> float:
    return round((done / total) * 100, 1) if total else 0.0


def create_health_report(db) -> dict:
    root = project_dir(db)
    blocks = list(db.blocks())
    scenes = list(db.scenes())
    visual_manager = VisualSlotManager(db)
    music_manager = SceneMusicManager(db)
    visual_plan = visual_manager.ensure_slot_folders()
    music_plan = music_manager.ensure_scene_folders()

    total_blocks = len(blocks)
    voice_done = sum(1 for b in blocks if approved_voice_path(db, b["id"]))
    visual_total = len(visual_plan.get("slots", []))
    visual_done = visual_manager.approved_count()
    music_total = len(music_plan.get("scenes", [])) or len(scenes)
    music_done = music_manager.approved_count()

    timeline_path = root / "production" / "timeline.json"
    timeline = {}
    if timeline_path.exists():
        try:
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        except Exception:
            timeline = {}

    renders = root / "renders"
    block_render_done = len(list((renders / "blocks").glob("*.txt"))) if (renders / "blocks").exists() else 0
    scene_render_done = len(list((renders / "scenes").glob("*.txt"))) if (renders / "scenes").exists() else 0
    export_done = (root / "exports" / "episode_v29_manifest.txt").exists()

    report = {
        "version": "v29_project_health",
        "project": str(db.path),
        "blocks": total_blocks,
        "scenes": len(scenes),
        "voice": {"done": voice_done, "total": total_blocks, "percent": _pct(voice_done, total_blocks)},
        "visual_slots": {"done": visual_done, "total": visual_total, "percent": _pct(visual_done, visual_total)},
        "scene_music": {"done": music_done, "total": music_total, "percent": _pct(music_done, music_total)},
        "timeline": {
            "exists": timeline_path.exists(),
            "ready_blocks": timeline.get("ready_blocks", 0),
            "total_blocks": timeline.get("total_blocks", total_blocks),
            "percent": _pct(int(timeline.get("ready_blocks", 0)), int(timeline.get("total_blocks", total_blocks) or total_blocks)),
        },
        "assembly": {
            "block_renders": block_render_done,
            "scene_renders": scene_render_done,
            "export_manifest": export_done,
        },
        "next_recommendation": next_recommendation(db, voice_done, total_blocks, visual_done, visual_total, music_done, music_total, timeline_path, export_done),
    }
    out = root / "production" / "health_report_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def next_recommendation(db, voice_done, total_blocks, visual_done, visual_total, music_done, music_total, timeline_path, export_done) -> dict:
    if voice_done < total_blocks:
        return {"task": "generate_missing_voices", "message": f"Generate/review voices: {voice_done}/{total_blocks} ready."}
    if visual_total == 0 or visual_done < visual_total:
        return {"task": "visual_slots", "message": f"Create/import visual slots: {visual_done}/{visual_total} ready."}
    if music_total and music_done < music_total:
        return {"task": "scene_music", "message": f"Create/import scene music: {music_done}/{music_total} ready."}
    if not timeline_path.exists():
        return {"task": "build_timeline", "message": "Build timeline.json."}
    if not export_done:
        return {"task": "build_episode", "message": "Build V29 episode manifest/render placeholders."}
    return {"task": "done", "message": "Project has a V29 export manifest."}
