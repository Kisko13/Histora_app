from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.block_state import approved_voice_path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _read_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _pct(done: int, total: int) -> int:
    return int(round((done / total) * 100)) if total else 0


def _bar(done: int, total: int, width: int = 24) -> str:
    if not total:
        return "░" * width
    filled = int(round((done / total) * width))
    return "█" * filled + "░" * max(0, width - filled)


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p and p.exists() and p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _approved_visual_slot_paths(root: Path) -> list[Path]:
    base = root / "assets" / "visual_slots"
    paths: list[Path] = []
    if not base.exists():
        return paths
    for slot_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        approved = _first_existing([slot_dir / f"approved{ext}" for ext in IMAGE_EXTS])
        if approved:
            paths.append(approved)
    return paths


def _approved_scene_music_paths(root: Path) -> list[Path]:
    base = root / "assets" / "scene_music"
    paths: list[Path] = []
    if not base.exists():
        return paths
    for scene_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        found = None
        for p in sorted(scene_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS and (p.stem.lower().startswith("approved") or p.name.lower().startswith("approved")):
                found = p
                break
        if found:
            paths.append(found)
    return paths


def _visual_plan_total(root: Path) -> int:
    plan = _read_json(root / "production" / "visual_slot_plan.json", {})
    slots = plan.get("visual_slots") or plan.get("slots") or []
    if isinstance(slots, list) and slots:
        return len(slots)
    # fallback: count dirs if plan absent
    base = root / "assets" / "visual_slots"
    return len([p for p in base.iterdir() if p.is_dir()]) if base.exists() else 0


def _scene_music_total(root: Path, db) -> int:
    plan = _read_json(root / "production" / "scene_music_plan.json", {})
    cues = plan.get("scene_music") or plan.get("music_cues") or plan.get("cues") or []
    if isinstance(cues, list) and cues:
        return len(cues)
    try:
        return len(db.scenes())
    except Exception:
        return 0


def _rendered_blocks(root: Path) -> list[Path]:
    blocks = root / "exports" / "v34_full_episode" / "blocks"
    if not blocks.exists():
        return []
    return sorted([p for p in blocks.glob("*.mp4") if p.is_file() and p.stat().st_size > 1024])


def _final_episode(root: Path) -> Path | None:
    candidates = [
        root / "exports" / "v34_full_episode" / "episode_v34_full.mp4",
        root / "exports" / "v34_full_episode" / "episode_v34_full_reencoded.mp4",
        root / "exports" / "v34_full_episode" / "episode_v34_test.mp4",
    ]
    return _first_existing(candidates)


def _latest_v34_report(root: Path) -> dict[str, Any]:
    return _read_json(root / "exports" / "v34_full_episode" / "v34_full_episode_render_report.json", {})


def _block_render_path(root: Path, block_id: str) -> Path:
    return root / "exports" / "v34_full_episode" / "blocks" / f"{block_id}.mp4"


def _block_health(db, root: Path, block) -> dict[str, Any]:
    bid = _get(block, "id", "")
    text = (_get(block, "text", "") or "").strip()
    voice = approved_voice_path(db, bid)
    rendered = _block_render_path(root, bid)
    render_ok = rendered.exists() and rendered.stat().st_size > 1024

    # In V28+ visuals and scene music are reusable episode-level assets, so block readiness
    # depends on whether the project-level libraries exist, not on per-block image/music.
    visual_slots_done = len(_approved_visual_slot_paths(root))
    visual_slots_total = max(1, _visual_plan_total(root))
    scene_music_done = len(_approved_scene_music_paths(root))
    scene_music_total = max(1, _scene_music_total(root, db))

    story_ok = bool(text)
    voice_ok = bool(voice)
    visuals_ok = visual_slots_done >= min(1, visual_slots_total)
    music_ok = scene_music_done >= min(1, scene_music_total)
    renderable = story_ok and visuals_ok  # voice fallback/silence is allowed, real voice is still tracked separately.
    final_ready = story_ok and voice_ok and visuals_ok and music_ok

    missing = []
    if not story_ok:
        missing.append("story")
    if not voice_ok:
        missing.append("approved_voice")
    if not visuals_ok:
        missing.append("visual_slot")
    if not music_ok:
        missing.append("scene_music")
    if not render_ok:
        missing.append("rendered_mp4")

    if render_ok and final_ready:
        status = "complete"
        next_task = "done"
    elif not voice_ok:
        status = "needs_voice_review"
        next_task = "generate/review/approve voice"
    elif not visuals_ok:
        status = "needs_visual_slot"
        next_task = "import/approve visual slot"
    elif not music_ok:
        status = "needs_scene_music"
        next_task = "import/approve scene music"
    elif not render_ok:
        status = "needs_render"
        next_task = "render episode/block"
    else:
        status = "ready"
        next_task = "ready"

    return {
        "block_id": bid,
        "scene_id": _get(block, "scene_id", ""),
        "scene_title": _get(block, "scene_title", ""),
        "character": _get(block, "character_id", ""),
        "title": (_get(block, "title", "") or _get(block, "scene_title", "") or bid),
        "story_ok": story_ok,
        "voice_ok": voice_ok,
        "visuals_ok": visuals_ok,
        "music_ok": music_ok,
        "render_ok": render_ok,
        "renderable": renderable,
        "final_ready": final_ready,
        "status": status,
        "next_task": next_task,
        "missing": missing,
        "voice_path": _rel(root, voice) if voice else "",
        "render_path": _rel(root, rendered) if render_ok else "",
        "word_count": len(text.split()),
    }


def build_v35_dashboard(db) -> dict[str, Any]:
    root = Path(db.root_dir)
    production = root / "production"
    exports = root / "exports"
    out_dir = exports / "v35_dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)

    blocks = list(db.blocks())
    total = len(blocks)
    block_rows = [_block_health(db, root, b) for b in blocks]

    voice_done = sum(1 for r in block_rows if r["voice_ok"])
    rendered_done = len(_rendered_blocks(root))
    renderable_done = sum(1 for r in block_rows if r["renderable"])
    final_ready_blocks = sum(1 for r in block_rows if r["final_ready"])

    visual_total = _visual_plan_total(root)
    visual_done = len(_approved_visual_slot_paths(root))
    music_total = _scene_music_total(root, db)
    music_done = len(_approved_scene_music_paths(root))

    episode = _final_episode(root)
    v34_report = _latest_v34_report(root)
    failures = v34_report.get("failures") or []
    concat_ok = bool(v34_report.get("concat_ok"))

    if episode and rendered_done >= total and concat_ok:
        next_action = "Episode rendered. Review final MP4, then replace placeholder voices/assets as needed."
    elif voice_done < total:
        next_action = f"Review/approve voices: {voice_done}/{total} approved."
    elif rendered_done < total:
        next_action = f"Render episode: {rendered_done}/{total} block MP4s exist."
    elif not concat_ok:
        next_action = "Run Render Episode again to concatenate final MP4."
    else:
        next_action = "Review final export package."

    status_counts: dict[str, int] = {}
    for r in block_rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    summary = {
        "blocks_total": total,
        "voices_approved": voice_done,
        "visual_slots_approved": visual_done,
        "visual_slots_total": visual_total,
        "scene_music_approved": music_done,
        "scene_music_total": music_total,
        "renderable_blocks": renderable_done,
        "final_ready_blocks": final_ready_blocks,
        "rendered_blocks": rendered_done,
        "episode_exists": bool(episode),
        "episode_mp4": str(episode) if episode else "",
        "concat_ok": concat_ok,
        "failed_blocks": len(failures),
        "next_action": next_action,
        "status_counts": status_counts,
    }

    report = {
        "version": "v35_production_dashboard",
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "summary": summary,
        "blocks": block_rows,
        "v34_report": str(root / "exports" / "v34_full_episode" / "v34_full_episode_render_report.json"),
    }

    report_path = production / "v35_dashboard_latest.json"
    _write_json(report_path, report)
    _write_json(out_dir / "dashboard.json", report)

    csv_path = out_dir / "block_health.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["block_id", "scene_title", "character", "status", "next_task", "story_ok", "voice_ok", "visuals_ok", "music_ok", "render_ok", "word_count", "voice_path", "render_path"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in block_rows:
            writer.writerow({k: r.get(k, "") for k in fields})

    html_path = out_dir / "dashboard.html"
    html_path.write_text(_dashboard_html(report), encoding="utf-8")

    report["report_path"] = str(report_path)
    report["html_path"] = str(html_path)
    report["csv_path"] = str(csv_path)
    return report


def build_v35_review_queue(db) -> dict[str, Any]:
    dashboard = build_v35_dashboard(db)
    root = Path(db.root_dir)
    out_dir = root / "exports" / "v35_dashboard"
    blocks = dashboard.get("blocks", [])

    priority = {
        "needs_voice_review": 10,
        "needs_visual_slot": 20,
        "needs_scene_music": 30,
        "needs_render": 40,
        "ready": 50,
        "complete": 99,
    }
    queue = sorted([b for b in blocks if b.get("status") != "complete"], key=lambda b: (priority.get(b.get("status"), 90), b.get("block_id", "")))

    queue_path = out_dir / "review_queue.json"
    queue_csv = out_dir / "review_queue.csv"
    queue_html = out_dir / "review_queue.html"

    _write_json(queue_path, {"version": "v35_review_queue", "built_at": datetime.now().isoformat(timespec="seconds"), "queue": queue})
    with queue_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["block_id", "scene_title", "character", "status", "next_task", "missing", "voice_path", "render_path"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in queue:
            row = {k: r.get(k, "") for k in fields}
            row["missing"] = ", ".join(r.get("missing", []))
            writer.writerow(row)

    queue_html.write_text(_queue_html(dashboard, queue), encoding="utf-8")
    return {
        "version": "v35_review_queue",
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "total_items": len(queue),
        "first_block_id": queue[0]["block_id"] if queue else "",
        "json_path": str(queue_path),
        "csv_path": str(queue_csv),
        "html_path": str(queue_html),
        "dashboard": dashboard,
    }


def _dashboard_html(report: dict[str, Any]) -> str:
    s = report["summary"]
    blocks = report.get("blocks", [])

    def card(title, done, total, subtitle=""):
        return f"""
        <div class=card>
          <h3>{html.escape(title)}</h3>
          <div class=num>{done}/{total} <span>{_pct(done,total)}%</span></div>
          <pre>{_bar(done,total)}</pre>
          <p>{html.escape(subtitle)}</p>
        </div>"""

    rows = "\n".join(
        f"<tr class='{html.escape(r['status'])}'><td>{html.escape(r['block_id'])}</td><td>{html.escape(r['scene_title'])}</td><td>{html.escape(r['character'])}</td><td>{html.escape(r['status'])}</td><td>{html.escape(r['next_task'])}</td><td>{'✓' if r['voice_ok'] else '—'}</td><td>{'✓' if r['render_ok'] else '—'}</td></tr>"
        for r in blocks[:300]
    )
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Histora V35 Dashboard</title>
<style>
body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:22px}} h1{{margin:0 0 12px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}} .card{{background:#1d1d1d;border:1px solid #333;border-radius:8px;padding:14px}} .num{{font-size:28px;font-weight:700}} .num span{{font-size:15px;color:#8bdcff}} pre{{color:#4cc2ff;font-size:18px;white-space:pre-wrap}} .next{{background:#202a20;border:1px solid #375f37;padding:14px;border-radius:8px;margin:16px 0}} table{{width:100%;border-collapse:collapse;margin-top:18px}} th,td{{border:1px solid #333;padding:7px;text-align:left}} th{{background:#222;color:#8bdcff}} tr.needs_voice_review td{{background:#231b12}} tr.needs_render td{{background:#182033}} tr.complete td{{background:#142414}} .path{{color:#aaa;font-size:12px}}
</style></head><body>
<h1>Histora V35 Production Dashboard</h1>
<div class=path>{html.escape(report.get('root',''))}</div>
<div class=next><b>Next action:</b> {html.escape(s.get('next_action',''))}</div>
<div class=grid>
{card('Voices approved', s['voices_approved'], s['blocks_total'], 'Real voice approval per block')}
{card('Visual slots', s['visual_slots_approved'], max(1,s['visual_slots_total']), 'Reusable images for the whole episode')}
{card('Scene music', s['scene_music_approved'], max(1,s['scene_music_total']), 'Scene/act-level music cues')}
{card('Renderable blocks', s['renderable_blocks'], s['blocks_total'], 'Story + usable visual assets')}
{card('Rendered block MP4s', s['rendered_blocks'], s['blocks_total'], 'V34 resume cache')}
{card('Final-ready blocks', s['final_ready_blocks'], s['blocks_total'], 'Voice + visuals + music + story')}
</div>
<h2>Episode</h2>
<p>Episode exists: <b>{'YES' if s['episode_exists'] else 'NO'}</b> | Concat OK: <b>{'YES' if s['concat_ok'] else 'NO'}</b> | Failures: <b>{s['failed_blocks']}</b></p>
<p class=path>{html.escape(s.get('episode_mp4',''))}</p>
<h2>Block Health</h2>
<table><tr><th>Block</th><th>Scene</th><th>Character</th><th>Status</th><th>Next task</th><th>Voice</th><th>Rendered</th></tr>{rows}</table>
</body></html>"""


def _queue_html(dashboard: dict[str, Any], queue: list[dict[str, Any]]) -> str:
    s = dashboard["summary"]
    rows = "\n".join(
        f"<tr><td>{i}</td><td>{html.escape(r['block_id'])}</td><td>{html.escape(r['scene_title'])}</td><td>{html.escape(r['character'])}</td><td>{html.escape(r['status'])}</td><td>{html.escape(r['next_task'])}</td><td>{html.escape(', '.join(r.get('missing', [])))}</td></tr>"
        for i, r in enumerate(queue[:500], 1)
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Histora V35 Review Queue</title>
<style>body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:22px}} table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:7px;text-align:left}} th{{background:#222;color:#8bdcff}} .next{{background:#241d14;border:1px solid #654;padding:12px;margin:12px 0;border-radius:8px}}</style>
</head><body><h1>Histora V35 Review Queue</h1><div class=next><b>Next action:</b> {html.escape(s.get('next_action',''))}</div><p>Queue items: {len(queue)}</p><table><tr><th>#</th><th>Block</th><th>Scene</th><th>Character</th><th>Status</th><th>Next task</th><th>Missing</th></tr>{rows}</table></body></html>"""


def latest_episode_path(db) -> str:
    p = _final_episode(Path(db.root_dir))
    return str(p) if p else ""
