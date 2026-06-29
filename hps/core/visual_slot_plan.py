from __future__ import annotations

import json
import math
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


def _block_words(block) -> int:
    return len((_get(block, "text", "") or "").split())


def _estimate_block_seconds(block) -> int:
    # Match existing app estimate roughly: listening-first narration with pauses.
    return max(6, int(_block_words(block) / 2.15))


def _scene_title_for_block(block) -> str:
    return _get(block, "scene_title", "Scene") or "Scene"


def create_visual_slot_plan(db, slot_count: int = 15) -> dict:
    """
    Create a listening-first visual plan.

    Voice remains block-based, but visuals are slot-based: 10-20 images across the whole
    episode, each covering a range of blocks/scenes. This is the right production model for
    long historical POV videos where the audience mostly listens.
    """
    blocks = list(db.blocks())
    slot_count = max(1, int(slot_count or 15))
    slot_count = min(slot_count, max(1, len(blocks)))

    total_seconds = sum(_estimate_block_seconds(b) for b in blocks) or 1
    target_seconds = total_seconds / slot_count

    slots = []
    current = []
    current_seconds = 0
    slot_index = 1

    for block in blocks:
        current.append(block)
        current_seconds += _estimate_block_seconds(block)
        if current_seconds >= target_seconds and slot_index < slot_count:
            slots.append(_make_slot(slot_index, current, current_seconds))
            slot_index += 1
            current = []
            current_seconds = 0

    if current:
        slots.append(_make_slot(slot_index, current, current_seconds))

    plan = {
        "version": "v28_visual_slots",
        "strategy": "listening_first_15_images",
        "requested_slot_count": slot_count,
        "actual_slot_count": len(slots),
        "total_blocks": len(blocks),
        "estimated_runtime_seconds": total_seconds,
        "slots": slots,
    }

    out = project_dir(db) / "production" / "visual_slot_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan


def _make_slot(index: int, blocks: list, seconds: int) -> dict:
    first = blocks[0]
    last = blocks[-1]
    scenes = []
    characters = []
    locations = []
    equipment = []
    text_parts = []

    for b in blocks:
        scene = _scene_title_for_block(b)
        if scene not in scenes:
            scenes.append(scene)
        char = _get(b, "character_id", "Narrator") or "Narrator"
        if char not in characters:
            characters.append(char)
        for field, target in [("image_prompt", text_parts), ("text", text_parts)]:
            val = (_get(b, field, "") or "").strip()
            if val:
                target.append(val)
        # crude extraction from prompt text so no new LLM is needed
        prompt = (_get(b, "image_prompt", "") or "").lower()
        for word in ["camp", "tent", "river", "plain", "road", "fire", "battlefield", "city", "farm", "hill"]:
            if word in prompt and word not in locations:
                locations.append(word)
        for word in ["shield", "sword", "helmet", "armor", "spear", "standard", "cloak"]:
            if word in prompt and word not in equipment:
                equipment.append(word)

    moment = " ".join(text_parts).replace("\n", " ")[:700]
    title = _slot_title(index, scenes, moment)
    prompt = (
        "cinematic historical POV still, listening-first YouTube documentary, "
        f"visual slot {index}, scenes: {', '.join(scenes[:3])}, "
        f"characters: {', '.join(characters[:4])}, "
        f"locations/objects: {', '.join((locations + equipment)[:8]) or 'period-correct environment'}, "
        "Roman Republic, Battle of Cannae context, grounded realism, natural light, "
        "human eye-level perspective, slow zoom friendly composition, no modern objects, no fantasy, "
        f"story moment: {moment}"
    )

    return {
        "id": f"VIS{index:03d}",
        "title": title,
        "start_block": _get(first, "id"),
        "end_block": _get(last, "id"),
        "block_ids": [_get(b, "id") for b in blocks],
        "scene_titles": scenes,
        "characters": characters,
        "duration_seconds": seconds,
        "prompt": prompt,
        "negative_prompt": "modern objects, fantasy armor, video game style, text, watermark, poster pose",
        "status": "planned",
    }


def _slot_title(index: int, scenes: list[str], moment: str) -> str:
    low = moment.lower()
    if "dawn" in low:
        return "Before Dawn"
    if "tent" in low:
        return "Inside the Tent"
    if "river" in low:
        return "Near the River"
    if "fire" in low:
        return "By the Fire"
    if "battle" in low or "shield" in low or "screaming" in low:
        return "Battlefield Tension"
    if "dead" in low or "after" in low:
        return "Aftermath"
    if scenes:
        return scenes[0]
    return f"Visual Slot {index:03d}"


def generate_mock_visual_slots(db, slot_count: int = 15, progress=None) -> dict:
    """
    Generate one mock placeholder per visual slot and assign block pointer files.
    This keeps production at ~15 images while making existing block status/progress work.
    """
    plan = create_visual_slot_plan(db, slot_count=slot_count)
    root = project_dir(db)
    visual_dir = root / "assets" / "visual_slots"
    visual_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for i, slot in enumerate(plan["slots"], 1):
        if progress:
            progress("visual_slot", slot["id"], i, len(plan["slots"]))
        slot_dir = visual_dir / slot["id"]
        slot_dir.mkdir(parents=True, exist_ok=True)
        slot_file = slot_dir / "approved.txt"
        slot_file.write_text(
            "MOCK VISUAL SLOT PLACEHOLDER — FREE/LOCAL\n\n"
            f"SLOT: {slot['id']}\nTITLE: {slot['title']}\n"
            f"COVERS: {slot['start_block']} -> {slot['end_block']}\n"
            f"DURATION: {slot['duration_seconds']} sec\n\n"
            f"PROMPT:\n{slot['prompt']}\n\nNEGATIVE:\n{slot['negative_prompt']}\n",
            encoding="utf-8",
        )
        slot["asset_path"] = str(slot_file.relative_to(root)).replace("\\", "/")
        slot["status"] = "generated"
        generated.append({"slot_id": slot["id"], "path": str(slot_file)})

        # Per-block pointer, not a duplicate image. Existing UI/progress sees approved.txt.
        for bid in slot["block_ids"]:
            if not bid:
                continue
            block_dir = root / "assets" / "images" / bid
            block_dir.mkdir(parents=True, exist_ok=True)
            pointer = block_dir / "approved.txt"
            pointer.write_text(
                "VISUAL SLOT POINTER — no per-block image generated\n\n"
                f"BLOCK: {bid}\nSLOT: {slot['id']}\nSLOT_FILE: {slot['asset_path']}\n"
                f"TITLE: {slot['title']}\n",
                encoding="utf-8",
            )
            try:
                db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (bid,))
            except Exception:
                pass

    plan["slots"] = plan["slots"]
    plan["generated_count"] = len(generated)
    out = root / "production" / "visual_slot_plan.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
