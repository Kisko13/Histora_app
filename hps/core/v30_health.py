
from __future__ import annotations

import json
from pathlib import Path

from hps.core.v29_health import create_health_report as create_v29_health_report
from hps.core.v29_asset_managers import project_dir


def create_v30_health_report(db) -> dict:
    root = project_dir(db)
    base = create_v29_health_report(db)
    subtitle_dir = root / "exports" / "subtitles"
    capcut_dir = root / "exports" / "capcut_v30"
    package_dir = root / "exports" / "episode_v30_package"
    report = {
        **base,
        "version": "v30_project_health",
        "v30": {
            "camera_plan": (root / "production" / "camera_plan.json").exists(),
            "srt": (subtitle_dir / "captions.srt").exists(),
            "vtt": (subtitle_dir / "captions.vtt").exists(),
            "ass": (subtitle_dir / "captions.ass").exists(),
            "capcut_csv": (capcut_dir / "timeline_import_plan.csv").exists(),
            "package_manifest": (package_dir / "episode_package_manifest.json").exists(),
            "report": (root / "production" / "v30_report_latest.json").exists(),
        },
    }
    if not report["v30"]["camera_plan"]:
        report["next_recommendation"] = {"task": "build_package", "message": "Build V30 package to create camera plan, subtitles, and CapCut CSV."}
    elif not report["v30"]["package_manifest"]:
        report["next_recommendation"] = {"task": "build_package", "message": "Finish V30 export package."}
    else:
        report["next_recommendation"] = {"task": "done", "message": "V30 package exists. Ready for manual edit/CapCut or future FFmpeg render."}
    out = root / "production" / "health_report_latest.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
