from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from hps.core.v29_asset_managers import project_dir
from hps.core.v29_timeline_engine import build_timeline
from hps.core.v31_asset_library import normalize_project_assets


def _fmt_time(seconds: int | float) -> str:
    seconds = int(seconds or 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def build_v31_timeline_preview(db, visual_slots: int = 15) -> dict:
    root = project_dir(db)
    normalize_project_assets(db, visual_slots=visual_slots, create_placeholders=True)
    timeline = build_timeline(db)

    out_dir = root / "exports" / "timeline_preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "timeline_preview.csv"
    html_path = out_dir / "timeline_preview.html"
    json_path = out_dir / "timeline_preview.json"

    blocks = timeline.get("blocks", [])
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "block_id", "scene_id", "start", "end", "duration", "character",
            "voice", "visual_slot", "visual", "scene_music", "music", "ready", "missing",
        ])
        writer.writeheader()
        for b in blocks:
            writer.writerow({
                "block_id": b.get("block_id", ""),
                "scene_id": b.get("scene_id", ""),
                "start": _fmt_time(b.get("start_seconds", 0)),
                "end": _fmt_time(b.get("end_seconds", 0)),
                "duration": b.get("duration_seconds", 0),
                "character": b.get("character", ""),
                "voice": b.get("voice_path", ""),
                "visual_slot": b.get("visual_slot_id", ""),
                "visual": b.get("visual_path", ""),
                "scene_music": b.get("scene_music_id", ""),
                "music": b.get("scene_music_path", ""),
                "ready": b.get("ready", False),
                "missing": ", ".join(b.get("missing", [])),
            })

    preview = {
        "version": "v31_timeline_preview",
        "timeline": "production/timeline.json",
        "runtime_minutes": timeline.get("runtime_minutes"),
        "total_blocks": timeline.get("total_blocks"),
        "ready_blocks": timeline.get("ready_blocks"),
        "csv": _rel(root, csv_path),
        "html": _rel(root, html_path),
        "blocks": blocks,
    }
    json_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")

    html_rows = []
    for b in blocks:
        status = "ready" if b.get("ready") else "missing"
        html_rows.append(
            "<tr class='%s'>" % status +
            f"<td>{html.escape(str(b.get('block_id','')))}</td>" +
            f"<td>{html.escape(str(b.get('scene_id','')))}</td>" +
            f"<td>{_fmt_time(b.get('start_seconds',0))}</td>" +
            f"<td>{_fmt_time(b.get('end_seconds',0))}</td>" +
            f"<td>{html.escape(str(b.get('character','')))}</td>" +
            f"<td>{html.escape(str(b.get('visual_slot_id','')))}</td>" +
            f"<td>{html.escape(str(b.get('scene_music_id','')))}</td>" +
            f"<td>{'✓' if b.get('voice_path') else '—'}</td>" +
            f"<td>{'✓' if b.get('visual_path') else '—'}</td>" +
            f"<td>{'✓' if b.get('scene_music_path') else '—'}</td>" +
            f"<td>{html.escape(', '.join(b.get('missing', [])))}</td>" +
            "</tr>"
        )

    scene_rows = []
    for s in timeline.get("scenes", []):
        scene_rows.append(
            f"<tr><td>{html.escape(str(s.get('scene_id','')))}</td>"
            f"<td>{html.escape(str(s.get('title','')))}</td>"
            f"<td>{_fmt_time(s.get('start_seconds',0))}</td>"
            f"<td>{_fmt_time(s.get('end_seconds',0))}</td>"
            f"<td>{s.get('ready_blocks',0)}/{s.get('total_blocks',0)}</td></tr>"
        )

    html_doc = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Histora V31 Timeline Preview</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#111;color:#ddd;margin:24px}}
h1,h2{{color:#fff}} .card{{background:#1d1d1d;border:1px solid #333;padding:14px;margin:12px 0;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border:1px solid #333;padding:6px;vertical-align:top}} th{{background:#222;color:#8fd3ff}}
tr.ready{{background:#102110}} tr.missing{{background:#2a1919}} .muted{{color:#aaa}}
</style></head><body>
<h1>Histora V31 Timeline Preview</h1>
<div class='card'>Runtime: <b>{timeline.get('runtime_minutes')}</b> min | Blocks: <b>{timeline.get('total_blocks')}</b> | Ready: <b>{timeline.get('ready_blocks')}</b></div>
<h2>Scenes</h2><table><tr><th>Scene</th><th>Title</th><th>Start</th><th>End</th><th>Ready</th></tr>{''.join(scene_rows)}</table>
<h2>Blocks</h2><table><tr><th>Block</th><th>Scene</th><th>Start</th><th>End</th><th>Character</th><th>Visual Slot</th><th>Scene Music</th><th>Voice</th><th>Visual</th><th>Music</th><th>Missing</th></tr>{''.join(html_rows)}</table>
<p class='muted'>This preview is generated from production/timeline.json. Replace placeholder slot/music files with approved real assets when ready.</p>
</body></html>"""
    html_path.write_text(html_doc, encoding="utf-8")

    return {
        "timeline": timeline,
        "csv": str(csv_path),
        "html": str(html_path),
        "json": str(json_path),
        "total_blocks": timeline.get("total_blocks", 0),
        "ready_blocks": timeline.get("ready_blocks", 0),
    }
