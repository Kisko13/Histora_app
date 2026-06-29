from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from hps.core.v29_asset_managers import project_dir
from hps.core.v29_timeline_engine import build_timeline
from hps.core.v30_camera_plan import create_camera_plan
from hps.core.v30_subtitles import generate_subtitles
from hps.core.v31_asset_library import normalize_project_assets
from hps.core.v31_timeline_preview import build_v31_timeline_preview


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _fmt_time(seconds: int | float) -> str:
    seconds = int(seconds or 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class V31ProductionPackage:
    """End-to-end V31 execution package.

    V31 consumes all previous plans and creates a real editable package over the full
    episode, not a demo subset. It is still render-safe and FFmpeg-ready: it creates
    complete manifests, preview HTML, subtitles, camera plan, CapCut CSV, and a draft
    FFmpeg script, but does not force final MP4 rendering.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.production = self.root / "production"
        self.exports = self.root / "exports"
        self.renders = self.root / "renders"

    def build(self, visual_slots: int = 15, progress=None) -> dict:
        total_steps = 8
        step = 0

        def tick(name: str, item: str):
            nonlocal step
            step += 1
            if progress:
                progress(name, item, step, total_steps)

        tick("assets", "normalize")
        asset_library = normalize_project_assets(self.db, visual_slots=visual_slots, create_placeholders=True)

        tick("timeline", "build")
        timeline = build_timeline(self.db)

        tick("camera", "plan")
        camera = create_camera_plan(self.db, timeline)

        tick("subtitles", "generate")
        subtitles = generate_subtitles(self.db, timeline)

        tick("preview", "html")
        preview = build_v31_timeline_preview(self.db, visual_slots=visual_slots)

        tick("assembly", "manifests")
        assembly = self._write_assembly_manifests(timeline, camera)

        tick("capcut", "csv")
        capcut = self._write_capcut_package(timeline, camera, subtitles)

        tick("package", "export")
        package = self._write_episode_package(timeline, camera, subtitles, preview, assembly, capcut, asset_library)

        report = {
            "version": "v31_execution_preview_package",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "policy": {
                "voice": "block_based",
                "visuals": "visual_slot_based",
                "music": "scene_based",
                "rendering": "manifest_preview_package_no_final_mp4_yet",
            },
            "timeline": {
                "runtime_minutes": timeline.get("runtime_minutes"),
                "total_blocks": timeline.get("total_blocks"),
                "ready_blocks": timeline.get("ready_blocks"),
                "path": "production/timeline.json",
            },
            "asset_library": asset_library,
            "camera": "production/camera_plan.json",
            "subtitles": subtitles,
            "preview": {k: v for k, v in preview.items() if k != "timeline"},
            "assembly": assembly,
            "capcut": capcut,
            "package": package,
        }
        out = self.production / "v31_report_latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(out)
        return report

    def _write_assembly_manifests(self, timeline: dict, camera: dict) -> dict:
        block_dir = self.renders / "blocks"
        scene_dir = self.renders / "scenes"
        block_dir.mkdir(parents=True, exist_ok=True)
        scene_dir.mkdir(parents=True, exist_ok=True)
        camera_by_block = {b.get("block_id"): b for b in camera.get("blocks", [])}
        blocks = timeline.get("blocks", [])
        scenes = timeline.get("scenes", [])

        block_outputs = []
        for b in blocks:
            bid = b.get("block_id", "block")
            cam = camera_by_block.get(bid, {})
            out = block_dir / f"{bid}_manifest.txt"
            out.write_text(
                "V31 BLOCK ASSEMBLY MANIFEST\n\n"
                f"BLOCK: {bid}\nSCENE: {b.get('scene_id')} — {b.get('scene_title')}\n"
                f"TIME: {_fmt_time(b.get('start_seconds',0))} -> {_fmt_time(b.get('end_seconds',0))}\n"
                f"DURATION: {b.get('duration_seconds')} sec\nCHARACTER: {b.get('character')}\n"
                f"READY: {b.get('ready')}\nMISSING: {', '.join(b.get('missing', []))}\n\n"
                f"VOICE: {b.get('voice_path')}\n"
                f"VISUAL SLOT: {b.get('visual_slot_id')} — {b.get('visual_title')}\n"
                f"VISUAL: {b.get('visual_path')}\n"
                f"SCENE MUSIC: {b.get('scene_music_id')} — {b.get('scene_music_title')}\n"
                f"MUSIC: {b.get('scene_music_path')}\n\n"
                f"CAMERA MOTION: {cam.get('motion','slow_zoom')} | {cam.get('pan','center')}\n"
                "FFMPEG FUTURE: create a video clip with visual loop, camera movement, narration, and low music bed.\n",
                encoding="utf-8",
            )
            block_outputs.append(_rel(self.root, out))

        by_block = {b.get("block_id"): b for b in blocks}
        scene_outputs = []
        for s in scenes:
            sid = s.get("scene_id", "scene")
            scene_blocks = [by_block.get(bid) for bid in s.get("block_ids", []) if by_block.get(bid)]
            out = scene_dir / f"{sid}_manifest.txt"
            lines = [
                "V31 SCENE ASSEMBLY MANIFEST",
                "",
                f"SCENE: {sid} — {s.get('title')}",
                f"TIME: {_fmt_time(s.get('start_seconds',0))} -> {_fmt_time(s.get('end_seconds',0))}",
                f"DURATION: {s.get('duration_seconds')} sec",
                f"BLOCKS: {len(scene_blocks)}",
                f"READY: {s.get('ready_blocks',0)}/{s.get('total_blocks',0)}",
                "",
            ]
            for b in scene_blocks:
                lines.append(f"- {b.get('block_id')} | voice={b.get('voice_path')} | visual={b.get('visual_slot_id')} | music={b.get('scene_music_id')} | missing={','.join(b.get('missing', []))}")
            out.write_text("\n".join(lines) + "\n", encoding="utf-8")
            scene_outputs.append(_rel(self.root, out))

        manifest_json = self.exports / "assembly_manifest.json"
        manifest_csv = self.exports / "assembly_manifest.csv"
        self.exports.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": "v31_assembly_manifest",
            "total_blocks": len(blocks),
            "total_scenes": len(scenes),
            "ready_blocks": sum(1 for b in blocks if b.get("ready")),
            "block_manifests": block_outputs,
            "scene_manifests": scene_outputs,
        }
        manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        with manifest_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["block_id", "scene_id", "start", "end", "duration", "voice", "visual", "music", "ready", "missing"])
            writer.writeheader()
            for b in blocks:
                writer.writerow({
                    "block_id": b.get("block_id", ""),
                    "scene_id": b.get("scene_id", ""),
                    "start": _fmt_time(b.get("start_seconds", 0)),
                    "end": _fmt_time(b.get("end_seconds", 0)),
                    "duration": b.get("duration_seconds", 0),
                    "voice": b.get("voice_path", ""),
                    "visual": b.get("visual_path", ""),
                    "music": b.get("scene_music_path", ""),
                    "ready": b.get("ready", False),
                    "missing": ", ".join(b.get("missing", [])),
                })
        return {
            "manifest_json": _rel(self.root, manifest_json),
            "manifest_csv": _rel(self.root, manifest_csv),
            "block_manifests": len(block_outputs),
            "scene_manifests": len(scene_outputs),
            "ready_blocks": manifest["ready_blocks"],
            "total_blocks": manifest["total_blocks"],
        }

    def _write_capcut_package(self, timeline: dict, camera: dict, subtitles: dict) -> dict:
        out_dir = self.exports / "capcut_v31"
        out_dir.mkdir(parents=True, exist_ok=True)
        camera_by_block = {b.get("block_id"): b for b in camera.get("blocks", [])}
        csv_path = out_dir / "timeline_import_plan.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["track", "block_id", "scene_id", "start", "end", "duration", "asset", "notes"])
            writer.writeheader()
            for b in timeline.get("blocks", []):
                cam = camera_by_block.get(b.get("block_id"), {})
                writer.writerow({"track":"voice", "block_id":b.get("block_id"), "scene_id":b.get("scene_id"), "start":b.get("start_seconds"), "end":b.get("end_seconds"), "duration":b.get("duration_seconds"), "asset":b.get("voice_path", ""), "notes":b.get("character", "")})
                writer.writerow({"track":"visual_slot", "block_id":b.get("block_id"), "scene_id":b.get("scene_id"), "start":b.get("start_seconds"), "end":b.get("end_seconds"), "duration":b.get("duration_seconds"), "asset":b.get("visual_path", ""), "notes":f"{b.get('visual_slot_id','')} | {cam.get('motion','')} | {cam.get('pan','')}"})
                if b.get("scene_music_path"):
                    writer.writerow({"track":"scene_music", "block_id":b.get("block_id"), "scene_id":b.get("scene_id"), "start":b.get("start_seconds"), "end":b.get("end_seconds"), "duration":b.get("duration_seconds"), "asset":b.get("scene_music_path", ""), "notes":b.get("scene_music_id", "")})
        readme = out_dir / "README_IMPORT_ORDER.txt"
        readme.write_text(
            "Histora V31 CapCut Import Package\n\n"
            "1. Import audio from assets/audio_raw.\n"
            "2. Import real images from assets/visual_slots/*/approved.png when available. Placeholder .txt files only document the slots.\n"
            "3. Import scene music from assets/scene_music/*/approved.mp3 when available.\n"
            "4. Import subtitles from exports/subtitles/captions.srt or captions.ass.\n"
            "5. Use timeline_import_plan.csv for timing and camera notes.\n",
            encoding="utf-8",
        )
        manifest = {
            "version": "v31_capcut_import_package",
            "timeline_csv": _rel(self.root, csv_path),
            "readme": _rel(self.root, readme),
            "subtitles": subtitles,
            "blocks": timeline.get("total_blocks"),
            "runtime_minutes": timeline.get("runtime_minutes"),
        }
        (out_dir / "capcut_package_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest

    def _write_episode_package(self, timeline: dict, camera: dict, subtitles: dict, preview: dict, assembly: dict, capcut: dict, asset_library: dict) -> dict:
        package = self.exports / "episode_v31_package"
        package.mkdir(parents=True, exist_ok=True)
        for src in [
            self.production / "timeline.json",
            self.production / "visual_slot_plan.json",
            self.production / "scene_music_plan.json",
            self.production / "camera_plan.json",
            self.production / "asset_library.json",
            self.exports / "timeline_preview" / "timeline_preview.html",
            self.exports / "timeline_preview" / "timeline_preview.csv",
            self.exports / "assembly_manifest.json",
            self.exports / "assembly_manifest.csv",
            self.exports / "subtitles" / "captions.srt",
            self.exports / "subtitles" / "captions.vtt",
            self.exports / "subtitles" / "captions.ass",
            self.exports / "capcut_v31" / "timeline_import_plan.csv",
            self.exports / "capcut_v31" / "README_IMPORT_ORDER.txt",
        ]:
            if src.exists():
                shutil.copy2(src, package / src.name)
        bat = package / "render_episode_ffmpeg_draft.bat"
        bat.write_text(
            "@echo off\n"
            "echo Histora V31 draft renderer placeholder.\n"
            "echo This package is ready for FFmpeg implementation; use assembly_manifest.csv and timeline.json.\n"
            "pause\n",
            encoding="utf-8",
        )
        readme = package / "README_EPISODE_PACKAGE.txt"
        readme.write_text(
            "Histora V31 Episode Package\n\n"
            f"Runtime: {timeline.get('runtime_minutes')} min\n"
            f"Blocks: {timeline.get('total_blocks')}\n"
            f"Ready blocks: {timeline.get('ready_blocks')}\n\n"
            "This package contains the full 125-block timeline, visual-slot plan, scene-music plan, subtitles, preview HTML, assembly manifests, and CapCut import CSV.\n"
            "It is the complete editing package. Final MP4 rendering is the next stage.\n",
            encoding="utf-8",
        )
        manifest = {
            "version": "v31_episode_package",
            "package_dir": _rel(self.root, package),
            "runtime_minutes": timeline.get("runtime_minutes"),
            "total_blocks": timeline.get("total_blocks"),
            "ready_blocks": timeline.get("ready_blocks"),
            "preview_html": preview.get("html", ""),
            "capcut_csv": capcut.get("timeline_csv", ""),
            "assembly_manifest": assembly.get("manifest_json", ""),
            "subtitles": subtitles,
        }
        (package / "episode_package_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest


def build_v31_production_package(db, visual_slots: int = 15, progress=None) -> dict:
    return V31ProductionPackage(db).build(visual_slots=visual_slots, progress=progress)
