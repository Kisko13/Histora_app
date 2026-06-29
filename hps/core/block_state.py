from pathlib import Path


AUDIO_EXTS = [".wav", ".mp3", ".m4a", ".txt", ""]
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".txt"]
MUSIC_EXTS = [".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".txt"]


def _exists_any(paths):
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


def approved_voice_path(db, block_id):
    rows = db.query(
        "SELECT * FROM audio_versions WHERE block_id=? AND status='approved' ORDER BY version DESC",
        (block_id,)
    )
    if rows:
        p = db.root_dir / rows[0]["path"]
        if p.exists():
            return p

    final_dir = db.root_dir / "assets" / "audio_final"
    return _exists_any([final_dir / f"{block_id}{ext}" for ext in AUDIO_EXTS])


def approved_image_path(db, block_id):
    d = db.root_dir / "assets" / "images" / block_id
    return _exists_any([d / f"approved{ext}" for ext in IMAGE_EXTS])


def approved_music_path(db, block_id):
    d = db.root_dir / "assets" / "music" / block_id
    if not d.exists():
        return None
    for p in d.iterdir():
        if p.is_file() and p.name.startswith("approved.") and p.suffix.lower() in MUSIC_EXTS:
            return p
    return None


def compute_block_state(db, block_id):
    block = db.block_with_scene(block_id)
    text = (block["text"] or "").strip()

    voice = approved_voice_path(db, block_id)
    image = approved_image_path(db, block_id)
    music = approved_music_path(db, block_id)

    story_ok = bool(text)
    voice_ok = bool(voice)
    image_ok = bool(image)
    music_ok = bool(music)

    missing = []
    if not story_ok:
        missing.append("story")
    if not voice_ok:
        missing.append("voice")
    if not image_ok:
        missing.append("image")
    if not music_ok:
        missing.append("music")

    # Production status uses hard requirements first.
    # Music is considered a production requirement for complete, but assembly-ready only needs voice + image.
    assembly_ready = story_ok and voice_ok and image_ok
    complete = story_ok and voice_ok and image_ok and music_ok

    if complete:
        status = "complete"
        next_task = "done"
    elif not story_ok:
        status = "missing_story"
        next_task = "write story"
    elif not voice_ok:
        status = "missing_voice"
        next_task = "generate/approve voice"
    elif not image_ok:
        status = "missing_image"
        next_task = "import/approve image"
    elif not music_ok:
        status = "missing_music"
        next_task = "import/approve music"
    else:
        status = "unknown"
        next_task = "review"

    icon = {
        "complete": "🟢",
        "missing_story": "🔴",
        "missing_voice": "🟠",
        "missing_image": "🟡",
        "missing_music": "🔵",
        "unknown": "⚪",
    }.get(status, "⚪")

    return {
        "block_id": block_id,
        "scene": block["scene_title"],
        "character": block["character_id"],
        "story_ok": story_ok,
        "voice_ok": voice_ok,
        "image_ok": image_ok,
        "music_ok": music_ok,
        "assembly_ready": assembly_ready,
        "complete": complete,
        "status": status,
        "status_label": status.replace("_", " ").upper(),
        "next_task": next_task,
        "missing": missing,
        "icon": icon,
        "voice_path": str(voice.relative_to(db.root_dir)).replace("\\", "/") if voice else "",
        "image_path": str(image.relative_to(db.root_dir)).replace("\\", "/") if image else "",
        "music_path": str(music.relative_to(db.root_dir)).replace("\\", "/") if music else "",
    }


def compute_project_state(db):
    states = [compute_block_state(db, b["id"]) for b in db.blocks()]
    total = len(states)
    complete = sum(1 for s in states if s["complete"])
    assembly_ready = sum(1 for s in states if s["assembly_ready"])
    voice_done = sum(1 for s in states if s["voice_ok"])
    image_done = sum(1 for s in states if s["image_ok"])
    music_done = sum(1 for s in states if s["music_ok"])

    next_state = None
    for s in states:
        if not s["complete"]:
            next_state = s
            break

    return {
        "total": total,
        "complete": complete,
        "assembly_ready": assembly_ready,
        "voice_done": voice_done,
        "image_done": image_done,
        "music_done": music_done,
        "states": states,
        "next": next_state,
    }
