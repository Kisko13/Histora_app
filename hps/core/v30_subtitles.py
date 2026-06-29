
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from hps.core.v29_asset_managers import project_dir


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _clean_caption(text: str) -> str:
    text = text or ""
    text = re.sub(r"(?m)^\s*\[[^\]]+\]\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")


def _ass_time(seconds: float) -> str:
    cs = int(round((seconds - int(seconds)) * 100))
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _wrap_caption(text: str, max_chars: int = 74) -> str:
    words = text.split()
    lines, cur = [], []
    for word in words:
        if cur and len(" ".join(cur + [word])) > max_chars:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines[:3])


def generate_subtitles(db, timeline: dict | None = None) -> dict:
    """Generate SRT, VTT, ASS and JSON captions from timeline blocks."""
    root = project_dir(db)
    if timeline is None:
        timeline_path = root / "production" / "timeline.json"
        if timeline_path.exists():
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        else:
            from hps.core.v29_timeline_engine import build_timeline
            timeline = build_timeline(db)

    caption_rows = []
    for block in timeline.get("blocks", []):
        bid = block.get("block_id")
        row = db.block(bid) if bid else None
        text = _clean_caption(_get(row, "text", "")) if row else ""
        if not text:
            text = f"[{bid}]"
        caption_rows.append({
            "index": len(caption_rows) + 1,
            "block_id": bid,
            "scene_id": block.get("scene_id"),
            "start_seconds": float(block.get("start_seconds") or 0),
            "end_seconds": float(block.get("end_seconds") or 0),
            "text": text,
            "wrapped_text": _wrap_caption(text),
        })

    out_dir = root / "exports" / "subtitles"
    out_dir.mkdir(parents=True, exist_ok=True)

    srt_lines = []
    for c in caption_rows:
        srt_lines.extend([
            str(c["index"]),
            f"{_srt_time(c['start_seconds'])} --> {_srt_time(c['end_seconds'])}",
            c["wrapped_text"],
            "",
        ])
    srt_path = out_dir / "captions.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    vtt_lines = ["WEBVTT", ""]
    for c in caption_rows:
        vtt_lines.extend([
            f"{_vtt_time(c['start_seconds'])} --> {_vtt_time(c['end_seconds'])}",
            c["wrapped_text"],
            "",
        ])
    vtt_path = out_dir / "captions.vtt"
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")

    ass_header = """[Script Info]\nTitle: Histora V30 Captions\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,3,1,2,120,120,70,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    ass_lines = [ass_header]
    for c in caption_rows:
        text = html.escape(c["wrapped_text"]).replace("\n", r"\N")
        ass_lines.append(f"Dialogue: 0,{_ass_time(c['start_seconds'])},{_ass_time(c['end_seconds'])},Default,,0,0,0,,{text}")
    ass_path = out_dir / "captions.ass"
    ass_path.write_text("\n".join(ass_lines), encoding="utf-8")

    json_path = out_dir / "captions.json"
    json_path.write_text(json.dumps({"version":"v30_captions", "captions": caption_rows}, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "caption_count": len(caption_rows),
        "srt": str(srt_path.relative_to(root)).replace("\\", "/"),
        "vtt": str(vtt_path.relative_to(root)).replace("\\", "/"),
        "ass": str(ass_path.relative_to(root)).replace("\\", "/"),
        "json": str(json_path.relative_to(root)).replace("\\", "/"),
    }
