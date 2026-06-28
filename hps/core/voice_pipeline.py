
from __future__ import annotations

import json
import re
import wave
import struct
import math
from pathlib import Path


TAG_RE = re.compile(r"(?m)^\s*\[[A-Za-z0-9 _.'-]+(?:\|[^\]]+)?\]\s*$")


def clean_voice_text(text: str) -> str:
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


def generate_voice_for_block(db, block_id: str, provider: str = "mock") -> dict:
    block = db.block(block_id)
    if not block:
        raise RuntimeError(f"Block not found: {block_id}")

    raw_text = block["text"] if "text" in block.keys() else ""
    clean_text = clean_voice_text(raw_text)
    assert_voice_text_safe(clean_text)

    character = block["character"] if "character" in block.keys() else "Narrator"

    project_path = Path(str(db.path))
    voice_dir = project_path.parent / "voices"
    voice_dir.mkdir(parents=True, exist_ok=True)

    safe_character = re.sub(r"[^A-Za-z0-9_-]+", "_", str(character)).strip("_").lower() or "narrator"
    audio_path = voice_dir / f"{block_id}_{safe_character}.wav"

    if provider.lower() in {"mock", "local_mock"}:
        make_mock_wav(audio_path, seconds=min(3.0, max(0.8, len(clean_text.split()) / 4)))
    else:
        # Real provider integration belongs here.
        # For now refuse unless existing provider code calls this module explicitly.
        raise RuntimeError(
            f"Provider '{provider}' is not connected in V26 voice pipeline yet. "
            "Use provider=mock for safety testing."
        )

    save_voice_request(audio_path, block_id, character, provider, clean_text)

    try:
        db.set_block_asset(block_id, "voice", str(audio_path), "generated")
    except Exception:
        try:
            db.update_block_asset(block_id, "voice", str(audio_path), "generated")
        except Exception:
            pass

    return {
        "block_id": block_id,
        "character": character,
        "provider": provider,
        "audio_path": str(audio_path),
        "voice_text": clean_text,
    }
