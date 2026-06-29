from __future__ import annotations

import json
from pathlib import Path

from hps.core.block_state import approved_voice_path
from hps.core.v29_asset_managers import SceneMusicManager, VisualSlotManager, project_dir


def create_v31_health_report(db) -> dict:
    root = project_dir(db)
    blocks = list(db.blocks())
    visual = VisualSlotManager(db)
    music = SceneMusicManager(db)
    timeline_path = root / "production" / "timeline.json"
    preview_path = root / "exports" / "timeline_preview" / "timeline_preview.html"
    package_path = root / "exports" / "episode_v31_package" / "episode_package_manifest.json"

    visual_slots = visual.load_plan().get("slots", [])
    scene_music = music.load_plan().get("scenes", [])
    voice_done = sum(1 for b in blocks if approved_voice_path(db, b["id"]))
    visual_done = sum(1 for s in visual_slots if visual.find_approved_slot_asset(s.get("id", "")))
    music_done = sum(1 for s in scene_music if music.find_approved_scene_asset(s.get("id", "")))

    timeline = {}
    if timeline_path.exists():
        try:
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        except Exception:
            timeline = {}

    block_manifest_count = len(list((root / "renders" / "blocks").glob("*_manifest.txt"))) if (root / "renders" / "blocks").exists() else 0
    scene_manifest_count = len(list((root / "renders" / "scenes").glob("*_manifest.txt"))) if (root / "renders" / "scenes").exists() else 0

    def pct(done, total):
        return round((done / total) * 100, 1) if total else 0.0

    if voice_done < len(blocks):
        nxt = {"task": "voices", "message": f"Generate/review voices: {voice_done}/{len(blocks)} ready."}
    elif visual_done < len(visual_slots):
        nxt = {"task": "visual_slots", "message": f"Replace or approve visual slots: {visual_done}/{len(visual_slots)} ready."}
    elif music_done < len(scene_music):
        nxt = {"task": "scene_music", "message": f"Replace or approve scene music: {music_done}/{len(scene_music)} ready."}
    elif not timeline_path.exists():
        nxt = {"task": "timeline", "message": "Build timeline."}
    elif not preview_path.exists():
        nxt = {"task": "preview", "message": "Build timeline preview."}
    elif not package_path.exists():
        nxt = {"task": "package", "message": "Build V31 package."}
    else:
        nxt = {"task": "done", "message": "V31 editing package exists. Ready for CapCut/manual edit or future final render."}

    report = {
        "version": "v31_health",
        "project": str(root),
        "blocks": {"total": len(blocks)},
        "voice": {"done": voice_done, "total": len(blocks), "percent": pct(voice_done, len(blocks))},
        "visual_slots": {"done": visual_done, "total": len(visual_slots), "percent": pct(visual_done, len(visual_slots))},
        "scene_music": {"done": music_done, "total": len(scene_music), "percent": pct(music_done, len(scene_music))},
        "timeline": {"exists": timeline_path.exists(), "total_blocks": timeline.get("total_blocks", 0), "ready_blocks": timeline.get("ready_blocks", 0), "runtime_minutes": timeline.get("runtime_minutes", 0)},
        "preview": {"html": preview_path.exists()},
        "assembly": {"block_manifests": block_manifest_count, "scene_manifests": scene_manifest_count, "full_block_coverage": block_manifest_count >= len(blocks) if blocks else False},
        "package": {"v31_package_manifest": package_path.exists()},
        "next_recommendation": nxt,
    }
    out = root / "production" / "health_report_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
