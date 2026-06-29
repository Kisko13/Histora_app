
from __future__ import annotations

import json
from pathlib import Path

from hps.core.v29_asset_managers import project_dir

MOTIONS = [
    {"motion": "slow_zoom_in", "scale_start": 1.00, "scale_end": 1.08, "pan": "center"},
    {"motion": "slow_zoom_out", "scale_start": 1.08, "scale_end": 1.00, "pan": "center"},
    {"motion": "pan_left", "scale_start": 1.06, "scale_end": 1.06, "pan": "right_to_left"},
    {"motion": "pan_right", "scale_start": 1.06, "scale_end": 1.06, "pan": "left_to_right"},
    {"motion": "slow_push_left", "scale_start": 1.02, "scale_end": 1.10, "pan": "center_to_left"},
    {"motion": "slow_push_right", "scale_start": 1.02, "scale_end": 1.10, "pan": "center_to_right"},
]


def create_camera_plan(db, timeline: dict | None = None) -> dict:
    """Create deterministic Ken Burns / pan movement metadata for timeline blocks.

    This does not render video. It gives the future FFmpeg/CapCut renderer a stable
    motion plan so the same project rebuilds consistently.
    """
    root = project_dir(db)
    if timeline is None:
        timeline_path = root / "production" / "timeline.json"
        if timeline_path.exists():
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        else:
            from hps.core.v29_timeline_engine import build_timeline
            timeline = build_timeline(db)

    blocks = timeline.get("blocks", [])
    plan_blocks = []
    slot_last_motion: dict[str, str] = {}

    for idx, block in enumerate(blocks):
        slot = block.get("visual_slot_id") or "slot_unknown"
        motion = MOTIONS[idx % len(MOTIONS)].copy()
        # Avoid exactly same movement twice in a row for the same slot.
        if slot_last_motion.get(slot) == motion["motion"]:
            motion = MOTIONS[(idx + 1) % len(MOTIONS)].copy()
        slot_last_motion[slot] = motion["motion"]

        duration = float(block.get("duration_seconds") or 6)
        fade = 0.75 if duration >= 8 else 0.35
        plan_blocks.append({
            "block_id": block.get("block_id"),
            "scene_id": block.get("scene_id"),
            "visual_slot_id": slot,
            "start_seconds": block.get("start_seconds"),
            "end_seconds": block.get("end_seconds"),
            "duration_seconds": duration,
            "visual_path": block.get("visual_path", ""),
            "motion": motion["motion"],
            "scale_start": motion["scale_start"],
            "scale_end": motion["scale_end"],
            "pan": motion["pan"],
            "fade_in_seconds": fade,
            "fade_out_seconds": fade,
            "transition": "crossfade" if idx else "none",
        })

    plan = {
        "version": "v30_camera_plan",
        "policy": "deterministic_ken_burns_for_reusable_visual_slots",
        "blocks": plan_blocks,
        "motions_available": [m["motion"] for m in MOTIONS],
    }
    out = root / "production" / "camera_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
