
from __future__ import annotations

import json
import re
from pathlib import Path

from hps.core.voice_pipeline import generate_voice_for_block


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def block_rows(db):
    return db.blocks()


def project_dir(db) -> Path:
    return Path(str(db.path)).parent


def ensure_character_library(db) -> Path:
    root = project_dir(db)
    path = root / "production" / "character_library.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    chars = {}
    for b in db.blocks():
        ch = str(b["character"] if "character" in b.keys() else "Narrator")
        key = _safe(ch)
        chars.setdefault(key, {
            "name": ch,
            "voice_provider": "mock",
            "voice_preset": "narrator_slow",
            "delivery": "Slow immersive historical POV narration; restrained, tired, human.",
            "image_continuity": "Keep character visually consistent across all generated images.",
        })

    path.write_text(json.dumps(chars, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def generate_missing_voices(db, provider="mock", limit=None):
    ensure_character_library(db)
    done = []

    for b in db.blocks():
        bid = b["id"]
        voice_status = b["voice_status"] if "voice_status" in b.keys() else ""
        if voice_status == "generated":
            continue

        result = generate_voice_for_block(db, bid, provider=provider)
        done.append(result)

        if limit and len(done) >= limit:
            break

    return done


def generate_mock_image_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")

    root = project_dir(db)
    out = root / "assets" / "images" / f"{block_id}_{_safe(b['character'])}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    prompt = ""
    try:
        prompt = b["image_prompt"]
    except Exception:
        prompt = f"Image prompt for {block_id}"

    out.write_text(
        "MOCK IMAGE PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\n"
        f"CHARACTER: {b['character']}\n\n"
        f"PROMPT:\n{prompt}\n",
        encoding="utf-8"
    )

    try:
        db.set_block_asset(block_id, "image", str(out), "generated")
    except Exception:
        pass

    return {"block_id": block_id, "image_path": str(out)}


def generate_missing_images(db, limit=None):
    done = []
    for b in db.blocks():
        bid = b["id"]
        image_status = b["image_status"] if "image_status" in b.keys() else ""
        if image_status == "generated":
            continue
        done.append(generate_mock_image_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done


def generate_mock_music_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")

    root = project_dir(db)
    out = root / "assets" / "music" / f"{block_id}_music.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    cue = ""
    try:
        cue = b["music_cue"]
    except Exception:
        cue = f"Music cue for {block_id}"

    out.write_text(
        "MOCK MUSIC PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\n"
        f"CHARACTER: {b['character']}\n\n"
        f"CUE:\n{cue}\n",
        encoding="utf-8"
    )

    try:
        db.set_block_asset(block_id, "music", str(out), "generated")
    except Exception:
        pass

    return {"block_id": block_id, "music_path": str(out)}


def generate_missing_music(db, limit=None):
    done = []
    for b in db.blocks():
        bid = b["id"]
        music_status = b["music_status"] if "music_status" in b.keys() else ""
        if music_status == "generated":
            continue
        done.append(generate_mock_music_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done
