from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hps.core.v29_timeline_engine import build_timeline
from hps.core.v29_health import create_health_report
from hps.core.v29_asset_managers import project_dir


class V29AssemblyEngine:
    """
    Timeline-driven assembly engine.

    This first production-safe implementation creates resume-friendly manifests and render
    placeholders. It does not require FFmpeg or real image/video assets, so the pipeline can
    be tested end-to-end with mock assets. Later, FFmpeg rendering can consume the same
    timeline.json and manifest files without changing upstream workflow.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.render_root = self.root / "renders"
        self.export_root = self.root / "exports"

    def build(self, progress=None) -> dict:
        timeline = build_timeline(self.db)
        blocks = timeline.get("blocks", [])
        scenes = timeline.get("scenes", [])
        total_steps = max(1, len(blocks) + len(scenes) + 1)
        step = 0

        block_outputs = []
        block_dir = self.render_root / "blocks"
        block_dir.mkdir(parents=True, exist_ok=True)
        for block in blocks:
            step += 1
            if progress:
                progress("render_block", block.get("block_id", ""), step, total_steps)
            out = block_dir / f"{block['block_id']}.txt"
            out.write_text(self._block_manifest_text(block), encoding="utf-8")
            block_outputs.append(str(out.relative_to(self.root)).replace("\\", "/"))

        scene_outputs = []
        scene_dir = self.render_root / "scenes"
        scene_dir.mkdir(parents=True, exist_ok=True)
        by_block = {b["block_id"]: b for b in blocks}
        for scene in scenes:
            step += 1
            if progress:
                progress("render_scene", scene.get("scene_id", ""), step, total_steps)
            out = scene_dir / f"{scene['scene_id']}.txt"
            scene_blocks = [by_block[b] for b in scene.get("block_ids", []) if b in by_block]
            out.write_text(self._scene_manifest_text(scene, scene_blocks), encoding="utf-8")
            scene_outputs.append(str(out.relative_to(self.root)).replace("\\", "/"))

        step += 1
        if progress:
            progress("export", "episode", step, total_steps)
        self.export_root.mkdir(parents=True, exist_ok=True)
        episode = self.export_root / "episode_v29_manifest.txt"
        episode.write_text(self._episode_manifest_text(timeline, block_outputs, scene_outputs), encoding="utf-8")

        try:
            project = self.db.project()
            if project:
                self.db.execute("UPDATE project SET assembly_status='approved', export_status='approved' WHERE id=?", (project["id"],))
        except Exception:
            pass

        health = create_health_report(self.db)
        report = {
            "version": "v29_assembly_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "timeline_path": str((self.root / "production" / "timeline.json").relative_to(self.root)).replace("\\", "/"),
            "block_outputs": block_outputs,
            "scene_outputs": scene_outputs,
            "episode_manifest": str(episode.relative_to(self.root)).replace("\\", "/"),
            "health": health,
        }
        report_path = self.root / "production" / "assembly_report_latest.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def _block_manifest_text(self, block: dict) -> str:
        return (
            "V29 BLOCK RENDER MANIFEST — placeholder/resume-safe\n\n"
            f"BLOCK: {block.get('block_id')}\n"
            f"SCENE: {block.get('scene_id')} — {block.get('scene_title')}\n"
            f"TIME: {block.get('start_seconds')} -> {block.get('end_seconds')} ({block.get('duration_seconds')} sec)\n"
            f"CHARACTER: {block.get('character')}\n\n"
            f"VOICE: {block.get('voice_path')}\n"
            f"VISUAL SLOT: {block.get('visual_slot_id')} — {block.get('visual_title')}\n"
            f"VISUAL: {block.get('visual_path')}\n"
            f"SCENE MUSIC: {block.get('scene_music_id')} — {block.get('scene_music_title')}\n"
            f"MUSIC: {block.get('scene_music_path')}\n\n"
            "FFMPEG FUTURE COMMAND:\n"
            "Use voice duration, loop visual with slow zoom/pan, mix low scene music bed.\n"
        )

    def _scene_manifest_text(self, scene: dict, blocks: list[dict]) -> str:
        lines = [
            "V29 SCENE RENDER MANIFEST — placeholder/resume-safe",
            "",
            f"SCENE: {scene.get('scene_id')} — {scene.get('title')}",
            f"TIME: {scene.get('start_seconds')} -> {scene.get('end_seconds')} ({scene.get('duration_seconds')} sec)",
            f"BLOCKS: {len(blocks)}",
            "",
        ]
        for block in blocks:
            lines.append(f"- {block.get('block_id')} | {block.get('voice_path')} | {block.get('visual_slot_id')} | {block.get('scene_music_id')}")
        return "\n".join(lines) + "\n"

    def _episode_manifest_text(self, timeline: dict, block_outputs: list[str], scene_outputs: list[str]) -> str:
        lines = [
            "V29 EPISODE MANIFEST — final assembly placeholder",
            "",
            f"RUNTIME: {timeline.get('runtime_minutes')} min ({timeline.get('runtime_seconds')} sec)",
            f"BLOCKS: {timeline.get('total_blocks')}",
            f"READY BLOCKS: {timeline.get('ready_blocks')}",
            "",
            "SCENE OUTPUTS:",
        ]
        lines.extend(f"- {p}" for p in scene_outputs)
        lines.append("")
        lines.append("BLOCK OUTPUTS:")
        lines.extend(f"- {p}" for p in block_outputs)
        lines.append("")
        lines.append("NEXT IMPLEMENTATION STEP: replace placeholder manifests with FFmpeg render commands.")
        return "\n".join(lines) + "\n"


def build_v29_episode(db, progress=None) -> dict:
    return V29AssemblyEngine(db).build(progress=progress)
