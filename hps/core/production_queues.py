from __future__ import annotations

import json
import re
from pathlib import Path

from hps.core.block_state import approved_image_path, approved_music_path, approved_voice_path
from hps.core.voice_pipeline import generate_voice_for_block


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def _row_get(row, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def project_dir(db) -> Path:
    return Path(str(db.path)).parent


def ensure_character_library(db) -> Path:
    root = project_dir(db)
    path = root / "production" / "character_library.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    chars: dict[str, dict] = {}
    for b in db.blocks():
        ch = str(_row_get(b, "character_id", "Narrator") or "Narrator")
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


def _set_image_generated(db, block_id: str):
    db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (block_id,))


def _set_music_generated(db, block_id: str):
    db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (block_id,))


def generate_missing_voices(db, provider="mock", limit=None, progress=None):
    ensure_character_library(db)
    done = []
    blocks = list(db.blocks())
    for b in blocks:
        bid = _row_get(b, "id")
        if not bid:
            continue
        if approved_voice_path(db, bid):
            continue
        # Skip already generated voice when user is testing missing-only batch; review/approve remains separate.
        if (_row_get(b, "status", "") or "") == "generated":
            continue
        if progress:
            progress("voice", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_voice_for_block(db, bid, provider=provider))
        if limit and len(done) >= limit:
            break
    return done


def generate_mock_image_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")
    char = _row_get(b, "character_id", "Narrator") or "Narrator"
    prompt = _row_get(b, "image_prompt", "") or f"Image prompt for {block_id}"

    out_dir = project_dir(db) / "assets" / "images" / block_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "approved.txt"
    out.write_text(
        "MOCK IMAGE PLACEHOLDER — FREE/LOCAL\n\n"
        f"BLOCK: {block_id}\nCHARACTER: {char}\n\nPROMPT:\n{prompt}\n",
        encoding="utf-8",
    )
    _set_image_generated(db, block_id)
    return {"block_id": block_id, "image_path": str(out)}


def generate_missing_images(db, limit=None, progress=None):
    done = []
    blocks = list(db.blocks())
    for b in blocks:
        bid = _row_get(b, "id")
        if not bid:
            continue
        if approved_image_path(db, bid):
            continue
        if progress:
            progress("image", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_mock_image_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done


def generate_mock_music_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")
    char = _row_get(b, "character_id", "Narrator") or "Narrator"
    cue = _row_get(b, "music_cue", "") or f"Music cue for {block_id}"

    out_dir = project_dir(db) / "assets" / "music" / block_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "approved.txt"
    out.write_text(
        "MOCK MUSIC PLACEHOLDER — FREE/LOCAL\n\n"
        f"BLOCK: {block_id}\nCHARACTER: {char}\n\nCUE:\n{cue}\n",
        encoding="utf-8",
    )
    _set_music_generated(db, block_id)
    return {"block_id": block_id, "music_path": str(out)}


def generate_missing_music(db, limit=None, progress=None):
    done = []
    blocks = list(db.blocks())
    for b in blocks:
        bid = _row_get(b, "id")
        if not bid:
            continue
        if approved_music_path(db, bid):
            continue
        if progress:
            progress("music", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_mock_music_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done
