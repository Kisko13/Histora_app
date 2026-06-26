"""
V24 local/free asset helpers.
No paid APIs are used here. These helpers create placeholder production assets,
prompt packs, cue sheets, manifests, and recovery files so the project can move
forward without spending money on anything except optional voice generation.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
import wave
from pathlib import Path
from typing import Iterable


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_solid_png(path: Path, width: int = 1920, height: int = 1080, rgb=(24, 24, 30)) -> Path:
    """Write a valid PNG using only the Python standard library."""
    path.parent.mkdir(parents=True, exist_ok=True)
    r, g, b = rgb
    # One scanline filter byte + RGB pixels. Reuse the row for compact zlib compression.
    row = bytes([0]) + bytes([r, g, b]) * width
    raw = row * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    path.write_bytes(data)
    return path


def create_image_placeholder(db, block_id: str, overwrite: bool = False) -> Path:
    """Create an approved placeholder image plus a detailed prompt text file."""
    block = db.block_with_scene(block_id)
    scene = db.scene_for_block(block_id)
    folder = db.root_dir / "assets" / "images" / block_id
    folder.mkdir(parents=True, exist_ok=True)
    png = folder / "approved.png"
    if overwrite or not png.exists():
        # Slight deterministic shade per block to avoid every placeholder being byte-identical.
        seed = sum(ord(c) for c in block_id) % 40
        write_solid_png(png, rgb=(22 + seed // 3, 24 + seed // 4, 32 + seed // 5))
    prompt = (block["image_prompt"] or "").strip()
    if not prompt:
        prompt = f"Cinematic historical POV still. Scene: {block['scene_title']}. Visual theme: {scene['visual_theme'] or 'grounded realistic historical detail'}. Moment: {(block['text'] or '')[:700]}"
        db.execute("UPDATE blocks SET image_prompt=? WHERE id=?", (prompt, block_id))
    (folder / "image_prompt.txt").write_text(prompt, encoding="utf-8")
    db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (block_id,))
    return png


def create_silent_wav(path: Path, seconds: float = 3.0, sample_rate: int = 44100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(seconds * sample_rate))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * frames)
    return path


def create_music_placeholder(db, block_id: str, overwrite: bool = False) -> Path:
    """Create an approved silent bed and cue sheet. This avoids paid music generation."""
    block = db.block_with_scene(block_id)
    folder = db.root_dir / "assets" / "music" / block_id
    folder.mkdir(parents=True, exist_ok=True)
    wav = folder / "approved.wav"
    seconds = max(3.0, len(block["text"] or "") / 13.0)
    if overwrite or not wav.exists():
        create_silent_wav(wav, seconds=min(seconds, 30.0))
    cue = (block["music_cue"] or "").strip()
    if not cue:
        cue = f"Local cue only, no paid generation: {block['scene_title']} | support narration, low volume, historically grounded atmosphere."
        db.execute("UPDATE blocks SET music_cue=? WHERE id=?", (cue, block_id))
    (folder / "music_cue.txt").write_text(cue, encoding="utf-8")
    db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (block_id,))
    return wav


def write_recovery_snapshot(db, label: str = "latest") -> Path:
    from hps.core.block_state import compute_project_state
    out = db.root_dir / "production_recovery"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": label,
        "project": dict(db.project()) if db.project() else {},
        "state": compute_project_state(db),
        "jobs": [dict(j) for j in db.production_jobs()] if hasattr(db, "production_jobs") else [],
    }
    path = out / f"{label}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_budget_forecast(db, provider: str = "qwen") -> Path:
    from hps.core.cost_control import estimate_voice_cost
    out = db.root_dir / "production_reports"
    out.mkdir(parents=True, exist_ok=True)
    blocks = db.blocks()
    chars = sum(len(b["text"] or "") for b in blocks)
    image_missing = sum(1 for b in blocks if not (db.root_dir / "assets" / "images" / b["id"] / "approved.png").exists())
    report = {
        "policy": "V24 Free-First: only voice may use a paid/API provider. Images, music, orchestration, assembly and reports are local/free.",
        "blocks": len(blocks),
        "characters": chars,
        "voice_provider": provider,
        "estimated_voice_cost_usd": round(estimate_voice_cost(chars, provider), 4),
        "estimated_image_cost_usd": 0.0,
        "estimated_music_cost_usd": 0.0,
        "estimated_orchestration_cost_usd": 0.0,
        "estimated_total_cost_usd": round(estimate_voice_cost(chars, provider), 4),
    }
    path = out / "v24_budget_forecast.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
