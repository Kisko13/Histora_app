
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from hps.core.v29_asset_managers import project_dir


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def create_capcut_import_plan(db, timeline: dict, camera_plan: dict, subtitles: dict) -> dict:
    """Create practical import CSVs/manifests for CapCut/manual editing."""
    root = project_dir(db)
    out_dir = root / "exports" / "capcut_v30"
    out_dir.mkdir(parents=True, exist_ok=True)
    camera_by_block = {b["block_id"]: b for b in camera_plan.get("blocks", [])}

    csv_path = out_dir / "timeline_import_plan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "track", "block_id", "scene_id", "start", "end", "duration", "asset", "notes",
        ])
        writer.writeheader()
        for b in timeline.get("blocks", []):
            cam = camera_by_block.get(b.get("block_id"), {})
            writer.writerow({
                "track": "voice",
                "block_id": b.get("block_id"),
                "scene_id": b.get("scene_id"),
                "start": b.get("start_seconds"),
                "end": b.get("end_seconds"),
                "duration": b.get("duration_seconds"),
                "asset": b.get("voice_path", ""),
                "notes": b.get("character", ""),
            })
            writer.writerow({
                "track": "visual",
                "block_id": b.get("block_id"),
                "scene_id": b.get("scene_id"),
                "start": b.get("start_seconds"),
                "end": b.get("end_seconds"),
                "duration": b.get("duration_seconds"),
                "asset": b.get("visual_path", ""),
                "notes": f"{b.get('visual_slot_id','')} | {cam.get('motion','')} | {cam.get('pan','')}",
            })
            if b.get("scene_music_path"):
                writer.writerow({
                    "track": "music_bed",
                    "block_id": b.get("block_id"),
                    "scene_id": b.get("scene_id"),
                    "start": b.get("start_seconds"),
                    "end": b.get("end_seconds"),
                    "duration": b.get("duration_seconds"),
                    "asset": b.get("scene_music_path", ""),
                    "notes": b.get("scene_music_id", ""),
                })

    readme_path = out_dir / "README_IMPORT_ORDER.txt"
    readme_path.write_text(
        "Histora V30 CapCut Import Package\n\n"
        "1. Import voice files from assets/audio_raw.\n"
        "2. Import visual slot approved images from assets/visual_slots.\n"
        "3. Import scene music from assets/scene_music.\n"
        "4. Import subtitles from exports/subtitles/captions.srt or captions.ass.\n"
        "5. Use timeline_import_plan.csv for start/end timing and motion notes.\n\n"
        "This is a production editing package, not a native CapCut project file yet.\n",
        encoding="utf-8"
    )

    manifest = {
        "version": "v30_capcut_import_package",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "timeline_csv": _rel(root, csv_path),
        "readme": _rel(root, readme_path),
        "subtitles": subtitles,
        "runtime_minutes": timeline.get("runtime_minutes"),
        "blocks": timeline.get("total_blocks"),
    }
    manifest_path = out_dir / "capcut_package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def create_export_package(db, timeline: dict, camera_plan: dict, subtitles: dict, capcut: dict, assembly: dict) -> dict:
    root = project_dir(db)
    package = root / "exports" / "episode_v30_package"
    package.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        root / "production" / "timeline.json",
        root / "production" / "camera_plan.json",
        root / "production" / "visual_slot_plan.json",
        root / "production" / "scene_music_plan.json",
        root / "production" / "health_report_latest.json",
        root / "production" / "assembly_report_latest.json",
        root / "exports" / "subtitles" / "captions.srt",
        root / "exports" / "subtitles" / "captions.vtt",
        root / "exports" / "subtitles" / "captions.ass",
        root / "exports" / "capcut_v30" / "timeline_import_plan.csv",
        root / "exports" / "capcut_v30" / "README_IMPORT_ORDER.txt",
    ]
    copied = []
    for src in files_to_copy:
        if src.exists():
            dst = package / src.name
            shutil.copy2(src, dst)
            copied.append(dst.name)

    readme = package / "README_EPISODE_PACKAGE.txt"
    readme.write_text(
        "Histora V30 Episode Package\n\n"
        f"Runtime: {timeline.get('runtime_minutes')} minutes\n"
        f"Blocks: {timeline.get('total_blocks')}\n"
        f"Ready blocks: {timeline.get('ready_blocks')}\n\n"
        "This package contains timeline, camera movement, subtitles, CapCut import CSV, and assembly reports.\n"
        "It does not contain a final MP4 yet. The next implementation step is FFmpeg/native renderer.\n",
        encoding="utf-8",
    )
    copied.append(readme.name)

    manifest = {
        "version": "v30_export_package",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_dir": _rel(root, package),
        "copied_files": copied,
        "capcut": capcut,
        "subtitles": subtitles,
        "assembly_report": assembly.get("report_path", ""),
    }
    manifest_path = package / "episode_package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
