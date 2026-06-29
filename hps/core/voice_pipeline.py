from __future__ import annotations

import json
import math
import re
import struct
import wave
from pathlib import Path

TAG_RE = re.compile(r"(?m)^\s*\[[A-Za-z0-9 _.'-]+(?:\|[^\]]+)?\]\s*$")


def _row_get(row, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def clean_voice_text(text: str) -> str:
    """Remove production-only speaker tags before paid or mock TTS."""
    text = text or ""
    text = TAG_RE.sub("", text)
    text = text.replace("ENDOFSCRIPT", "")
    text = re.sub(r"(?m)^echo\s+[\"']?Done[\"']?\s*$", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def assert_voice_text_safe(text: str):
    if TAG_RE.search(text or ""):
        raise RuntimeError("Voice text still contains speaker tags. Refusing paid voice generation.")
    if not (text or "").strip():
        raise RuntimeError("Voice text is empty.")


def make_mock_wav(path: Path, seconds: float = 1.0, freq: float = 440.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 22050
    frames = int(rate * seconds)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(frames):
            value = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", value))


def save_voice_request(path: Path, block_id: str, character: str, provider: str, text: str):
    request = {
        "block_id": block_id,
        "character": character,
        "provider": provider,
        "voice_text": text,
        "paid_step": provider.lower() not in {"mock", "local_mock"},
        "speaker_tags_removed": True,
    }
    json_path = path.with_name(path.stem + "_voice_request.json")
    json_path.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_version(db, block_id: str) -> int:
    return (db.scalar("SELECT MAX(version) FROM audio_versions WHERE block_id=?", (block_id,)) or 0) + 1


def generate_voice_for_block(db, block_id: str, provider: str = "mock") -> dict:
    """
    Generate voice for one block through the V26-safe text path.

    Current production implementation supports mock/local_mock only. Real paid providers
    should be integrated here so every paid call passes through clean_voice_text() and
    assert_voice_text_safe().
    """
    block = db.block(block_id)
    if not block:
        raise RuntimeError(f"Block not found: {block_id}")

    raw_text = _row_get(block, "text", "") or ""
    clean_text = clean_voice_text(raw_text)
    assert_voice_text_safe(clean_text)

    character = _row_get(block, "character_id", "Narrator") or "Narrator"
    project_id = _row_get(block, "project_id", db.project_id())
    version = _next_version(db, block_id)

    voice_dir = db.root_dir / "assets" / "audio_raw"
    voice_dir.mkdir(parents=True, exist_ok=True)
    safe_character = re.sub(r"[^A-Za-z0-9_-]+", "_", str(character)).strip("_").lower() or "narrator"
    audio_path = voice_dir / f"{block_id}_{safe_character}_v{version:03d}.wav"

    provider_key = (provider or "mock").lower()
    if provider_key in {"mock", "local_mock"}:
        make_mock_wav(audio_path, seconds=min(3.0, max(0.8, len(clean_text.split()) / 4)))
    else:
        raise RuntimeError(
            f"Provider '{provider}' is not connected in V27.1 voice pipeline yet. "
            "Use provider=mock for safe testing."
        )

    save_voice_request(audio_path, block_id, character, provider_key, clean_text)
    rel = str(audio_path.relative_to(db.root_dir)).replace("\\", "/")
    db.execute(
        "INSERT INTO audio_versions(project_id, block_id, version, provider, path, status, char_count, estimated_cost_usd) "
        "VALUES (?, ?, ?, ?, ?, 'generated', ?, 0)",
        (project_id, block_id, version, provider_key, rel, len(clean_text)),
    )
    db.execute("UPDATE blocks SET status='generated', issue='' WHERE id=?", (block_id,))

    return {
        "block_id": block_id,
        "character": character,
        "provider": provider_key,
        "audio_path": str(audio_path),
        "audio_rel_path": rel,
        "voice_text": clean_text,
        "version": version,
    }
