from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def project_dir(db) -> Path:
    return Path(str(db.path)).parent


def create_scene_music_plan(db) -> dict:
    scenes = list(db.scenes())
    blocks = list(db.blocks())
    blocks_by_scene = {}
    for b in blocks:
        blocks_by_scene.setdefault(_get(b, "scene_id"), []).append(b)

    music_scenes = []
    for scene in scenes:
        sid = _get(scene, "id")
        scene_blocks = blocks_by_scene.get(sid, [])
        text = " ".join((_get(b, "text", "") or "") for b in scene_blocks)[:1000]
        cue = _scene_music_cue(scene, text)
        duration = sum(max(6, int(len((_get(b, "text", "") or "").split()) / 2.15)) for b in scene_blocks)
        music_scenes.append({
            "id": sid,
            "title": _get(scene, "title", sid),
            "block_ids": [_get(b, "id") for b in scene_blocks],
            "duration_seconds": duration,
            "cue": cue,
            "status": "planned",
        })

    plan = {
        "version": "v28_scene_music",
        "strategy": "scene_based_music_not_per_block",
        "scene_count": len(music_scenes),
        "scenes": music_scenes,
    }
    out = project_dir(db) / "production" / "scene_music_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan


def _scene_music_cue(scene, text: str) -> str:
    title = _get(scene, "title", "Scene")
    low = (title + " " + text).lower()
    if "battle" in low or "shield" in low or "screaming" in low:
        mood = "low battle tension, restrained percussion, distant dread"
    elif "dawn" in low or "morning" in low:
        mood = "quiet dawn tension, sparse drones, slow pulse"
    elif "tent" in low:
        mood = "claustrophobic tent ambience, low strings, muted unease"
    elif "river" in low:
        mood = "river approach, slow ominous movement, wind and water bed"
    elif "fire" in low:
        mood = "campfire memory, quiet crackle, warm but uneasy drone"
    else:
        mood = "subtle historical ambience under narration"
    return f"SCENE MUSIC ONLY, not per block. {title}: {mood}. Keep low under narration, loopable, no vocals."


def generate_mock_scene_music(db, progress=None) -> dict:
    plan = create_scene_music_plan(db)
    root = project_dir(db)
    scene_music_dir = root / "assets" / "scene_music"
    scene_music_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for i, scene in enumerate(plan["scenes"], 1):
        if progress:
            progress("scene_music", scene["id"], i, len(plan["scenes"]))
        out_dir = scene_music_dir / scene["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "approved.txt"
        out.write_text(
            "MOCK SCENE MUSIC PLACEHOLDER — FREE/LOCAL\n\n"
            f"SCENE: {scene['id']}\nTITLE: {scene['title']}\n"
            f"DURATION: {scene['duration_seconds']} sec\n\nCUE:\n{scene['cue']}\n",
            encoding="utf-8",
        )
        scene["asset_path"] = str(out.relative_to(root)).replace("\\", "/")
        scene["status"] = "generated"
        generated.append({"scene_id": scene["id"], "path": str(out)})

        # Per-block pointer for current UI/progress; actual assembly should use scene_music_plan.json.
        for bid in scene["block_ids"]:
            if not bid:
                continue
            block_dir = root / "assets" / "music" / bid
            block_dir.mkdir(parents=True, exist_ok=True)
            pointer = block_dir / "approved.txt"
            pointer.write_text(
                "SCENE MUSIC POINTER — no per-block music generated\n\n"
                f"BLOCK: {bid}\nSCENE: {scene['id']}\nSCENE_MUSIC_FILE: {scene['asset_path']}\n",
                encoding="utf-8",
            )
            try:
                db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (bid,))
            except Exception:
                pass

    plan["generated_count"] = len(generated)
    out = root / "production" / "scene_music_plan.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
