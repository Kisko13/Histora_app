
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hps.core.v29_timeline_engine import build_timeline
from hps.core.v29_assembly_engine import build_v29_episode
from hps.core.v29_health import create_health_report
from hps.core.v29_asset_managers import project_dir
from hps.core.v30_camera_plan import create_camera_plan
from hps.core.v30_subtitles import generate_subtitles
from hps.core.v30_capcut_package import create_capcut_import_plan, create_export_package


class V30AssemblyEngine:
    """V30 production assembly package builder.

    Creates the first real editing package:
    - timeline.json
    - camera_plan.json
    - block/scene/episode manifests
    - captions.srt/.vtt/.ass
    - CapCut/manual import CSV
    - episode package manifest

    Still render-safe: it does not require FFmpeg or real video rendering yet.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)

    def build(self, progress=None) -> dict:
        total = 6
        step = 0
        def tick(name, item):
            nonlocal step
            step += 1
            if progress:
                progress(name, item, step, total)

        tick("timeline", "episode")
        timeline = build_timeline(self.db)

        tick("camera", "ken_burns")
        camera = create_camera_plan(self.db, timeline)

        tick("subtitles", "captions")
        subtitles = generate_subtitles(self.db, timeline)

        tick("assembly", "manifests")
        assembly = build_v29_episode(self.db, progress=None)

        tick("capcut", "import_plan")
        capcut = create_capcut_import_plan(self.db, timeline, camera, subtitles)

        tick("package", "episode")
        package = create_export_package(self.db, timeline, camera, subtitles, capcut, assembly)

        health = create_health_report(self.db)
        report = {
            "version": "v30_assembly_package_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "timeline": "production/timeline.json",
            "camera_plan": "production/camera_plan.json",
            "subtitles": subtitles,
            "capcut": capcut,
            "assembly": assembly,
            "package": package,
            "health": health,
        }
        out = self.root / "production" / "v30_report_latest.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(out)
        return report


def build_v30_episode_package(db, progress=None) -> dict:
    return V30AssemblyEngine(db).build(progress=progress)
