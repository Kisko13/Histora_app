from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.v33_renderer import V33Renderer, _ffmpeg_exe


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _write_concat_file(path: Path, files: list[Path]) -> None:
    """Write an FFmpeg concat-demuxer file with Windows-safe absolute paths."""
    lines = []
    for f in files:
        # concat demuxer accepts forward slashes on Windows and is much less painful that way.
        s = f.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{s}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class V34FullEpisodeRenderer:
    """V34: resumable full episode renderer.

    Builds on the proven V33 block renderer and adds:
    - render all blocks, not just a test subset
    - resume: skip existing block MP4s unless force=True
    - per-block render status report
    - full episode concatenation
    - failure does not destroy completed block renders
    - render scripts/reports saved for debugging and reproducibility
    """

    def __init__(self, db):
        self.db = db
        self.v33 = V33Renderer(db)
        self.root = self.v33.root
        self.production = self.root / "production"
        self.exports = self.root / "exports"
        self.render_dir = self.exports / "v34_full_episode"
        self.blocks_dir = self.render_dir / "blocks"
        self.logs_dir = self.render_dir / "logs"
        self.app_root = self.v33.app_root

    def _load_or_build_jobs(self, visual_slots: int = 15) -> list[dict[str, Any]]:
        # Always rebuild the V33 package first so current approved assets/timeline are reflected.
        self.v33.build_render_package(visual_slots=visual_slots)
        manifest_path = self.exports / "v33_render" / "v33_render_manifest.json"
        if not manifest_path.exists():
            raise RuntimeError(f"Missing V33 render manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jobs = list(manifest.get("block_jobs", []))
        if not jobs:
            raise RuntimeError("V33 render manifest contains no block jobs.")
        return jobs

    def build_full_episode_package(self, visual_slots: int = 15) -> dict[str, Any]:
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        jobs = self._load_or_build_jobs(visual_slots=visual_slots)

        # Rewrite outputs into v34 folder so V33 previews and V34 full renders don't collide.
        for j in jobs:
            bid = j.get("block_id") or "block"
            out = self.blocks_dir / f"{bid}.mp4"
            j["v34_output_abs"] = str(out)
            j["v34_output"] = _rel(self.root, out)

        manifest = {
            "version": "v34_full_episode_render_package",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "total_blocks": len(jobs),
            "ffmpeg": _ffmpeg_exe(self.app_root),
            "resume_policy": "existing block mp4 files are skipped unless force render is requested",
            "outputs": {
                "blocks_dir": str(self.blocks_dir),
                "episode_mp4": str(self.render_dir / "episode_v34_full.mp4"),
                "concat_file": str(self.render_dir / "concat_v34.txt"),
            },
            "block_jobs": jobs,
        }
        manifest_path = self.render_dir / "v34_full_episode_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        bat = self.render_dir / "render_v34_full_episode.bat"
        bat.write_text(
            "@echo off\n"
            "echo Histora V34 Full Episode Render\n"
            "echo Use the Studio button for progress/resume.\n"
            "echo Manifest:\n"
            f"echo {manifest_path}\n"
            "pause\n",
            encoding="utf-8",
        )

        report = {
            "version": "v34_package_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "total_blocks": len(jobs),
            "manifest": str(manifest_path),
            "render_dir": str(self.render_dir),
            "blocks_dir": str(self.blocks_dir),
            "episode_mp4": str(self.render_dir / "episode_v34_full.mp4"),
        }
        report_path = self.production / "v34_report_latest.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def render_full_episode(
        self,
        visual_slots: int = 15,
        max_blocks: int | None = None,
        resume: bool = True,
        force: bool = False,
        progress=None,
    ) -> dict[str, Any]:
        package = self.build_full_episode_package(visual_slots=visual_slots)
        manifest_path = Path(package["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jobs = list(manifest.get("block_jobs", []))
        if max_blocks and max_blocks > 0:
            jobs = jobs[:max_blocks]

        rendered: list[Path] = []
        statuses: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        total_steps = len(jobs) + 1

        for i, job in enumerate(jobs, 1):
            bid = job.get("block_id") or f"block_{i:04d}"
            out = Path(job.get("v34_output_abs") or (self.blocks_dir / f"{bid}.mp4"))
            if progress:
                progress("render_block", bid, i, total_steps)

            if resume and out.exists() and out.stat().st_size > 1024 and not force:
                rendered.append(out)
                statuses.append({"block_id": bid, "status": "skipped_existing", "output": str(out)})
                continue

            try:
                ok, mode = self.v33._run_ffmpeg_with_fallback(job, out, self.logs_dir)
                if ok:
                    rendered.append(out)
                    statuses.append({
                        "block_id": bid,
                        "status": "rendered",
                        "mode": mode,
                        "duration_seconds": job.get("duration_seconds"),
                        "output": str(out),
                    })
            except Exception as exc:
                failure = {"block_id": bid, "status": "failed", "error": str(exc), "output": str(out)}
                failures.append(failure)
                statuses.append(failure)
                # V34 is a production renderer: stop on first failure so the user can fix/resume.
                break

        concat_file = self.render_dir / "concat_v34.txt"
        episode_out = self.render_dir / ("episode_v34_test.mp4" if max_blocks else "episode_v34_full.mp4")
        concat_ok = False
        concat_error = ""

        if rendered and not failures:
            if progress:
                progress("concat_episode", episode_out.name, total_steps, total_steps)
            _write_concat_file(concat_file, rendered)
            proc = subprocess.run(
                [_ffmpeg_exe(self.app_root), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(episode_out)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode == 0:
                concat_ok = True
            else:
                # Re-encode fallback handles rare codec/timebase mismatches between blocks.
                reencode_out = episode_out.with_name(episode_out.stem + "_reencoded.mp4")
                proc2 = subprocess.run(
                    [_ffmpeg_exe(self.app_root), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", str(reencode_out)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if proc2.returncode == 0:
                    episode_out = reencode_out
                    concat_ok = True
                else:
                    concat_error = proc.stderr + "\n\nREENCODE STDERR:\n" + proc2.stderr
                    (self.logs_dir / "concat_v34_error.log").write_text(concat_error, encoding="utf-8", errors="ignore")
                    failures.append({"stage": "concat", "error": str(self.logs_dir / "concat_v34_error.log")})

        report = {
            "version": "v34_full_episode_render_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "requested_blocks": len(jobs),
            "rendered_or_existing_blocks": len(rendered),
            "failed_blocks": len(failures),
            "concat_ok": concat_ok,
            "episode_mp4": str(episode_out) if concat_ok else "",
            "concat_file": str(concat_file),
            "render_dir": str(self.render_dir),
            "blocks_dir": str(self.blocks_dir),
            "logs_dir": str(self.logs_dir),
            "resume": resume,
            "force": force,
            "statuses": statuses,
            "failures": failures,
        }
        report_path = self.render_dir / "v34_full_episode_render_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.production / "v34_report_latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report


def build_v34_full_episode_package(db, visual_slots: int = 15) -> dict[str, Any]:
    return V34FullEpisodeRenderer(db).build_full_episode_package(visual_slots=visual_slots)


def render_v34_full_episode(db, visual_slots: int = 15, max_blocks: int | None = None, resume: bool = True, force: bool = False, progress=None) -> dict[str, Any]:
    return V34FullEpisodeRenderer(db).render_full_episode(visual_slots=visual_slots, max_blocks=max_blocks, resume=resume, force=force, progress=progress)
