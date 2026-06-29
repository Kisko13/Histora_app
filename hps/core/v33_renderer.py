
from __future__ import annotations

import csv
import json
import os
import shutil
import struct
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.v29_asset_managers import SceneMusicManager, VisualSlotManager, project_dir
from hps.core.v29_timeline_engine import build_timeline
from hps.core.v31_asset_library import normalize_project_assets
from hps.core.v31_timeline_preview import build_v31_timeline_preview
from hps.core.v31_assembly_package import build_v31_production_package

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _abs(root: Path, p: str | Path | None) -> Path | None:
    if not p:
        return None
    p = Path(p)
    return p if p.is_absolute() else root / p


def _q(p: Path | str) -> str:
    return '"' + str(p).replace('"', '') + '"'


def _project_root_from_project_dir(project_root: Path) -> Path:
    try:
        return project_root.parents[1]
    except Exception:
        return Path.cwd()


def _read_env_file(app_root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in [app_root / ".env", Path.cwd() / ".env"]:
        if not candidate.exists():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            pass
    return env


def _ffmpeg_candidates(app_root: Path | None = None) -> list[str]:
    app_root = app_root or Path.cwd()
    env_file = _read_env_file(app_root)
    candidates: list[str] = []

    if os.environ.get("FFMPEG_EXE"):
        candidates.append(os.environ["FFMPEG_EXE"])
    if env_file.get("FFMPEG_EXE"):
        candidates.append(env_file["FFMPEG_EXE"])

    candidates += [
        str(app_root / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(app_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(app_root / "bin" / "ffmpeg.exe"),
    ]

    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    out: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        c = str(c).strip()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _ffmpeg_exe(app_root: Path | None = None) -> str:
    for c in _ffmpeg_candidates(app_root):
        p = Path(c)
        if p.exists() and p.is_file():
            return str(p)
        if c.lower() == "ffmpeg" or shutil.which(c):
            return c
    checked = "\n".join(_ffmpeg_candidates(app_root)) or "No candidates."
    raise RuntimeError("FFmpeg not found. Set FFMPEG_EXE in .env to the full ffmpeg.exe path.\n\nChecked:\n" + checked)


def _ffprobe_exe(app_root: Path | None = None) -> str | None:
    ff = Path(_ffmpeg_exe(app_root))
    if ff.name.lower() == "ffmpeg.exe":
        fp = ff.with_name("ffprobe.exe")
        if fp.exists():
            return str(fp)
    found = shutil.which("ffprobe")
    return found


def _bmp_24(path: Path, width: int = 1920, height: int = 1080, seed: int = 0):
    path.parent.mkdir(parents=True, exist_ok=True)
    row_pad = (4 - (width * 3) % 4) % 4
    row_size = width * 3 + row_pad
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size
    base_r = 34 + (seed * 31) % 80
    base_g = 30 + (seed * 17) % 70
    base_b = 26 + (seed * 13) % 65
    with path.open("wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(b"\x00\x00\x00\x00")
        f.write(struct.pack("<I", 54))
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", width))
        f.write(struct.pack("<i", height))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 24))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", pixel_data_size))
        f.write(struct.pack("<i", 2835))
        f.write(struct.pack("<i", 2835))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", 0))
        for y in range(height):
            shade = int(45 * (y / max(1, height - 1)))
            r = max(0, min(255, base_r + shade))
            g = max(0, min(255, base_g + shade))
            b = max(0, min(255, base_b + shade))
            row = bytes([b, g, r]) * width + (b"\x00" * row_pad)
            f.write(row)


def _silence_wav(path: Path, seconds: float, rate: int = 48000):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(rate * max(0.1, seconds)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        chunk = b"\x00\x00" * min(rate, frames)
        remaining = frames
        while remaining > 0:
            n = min(len(chunk) // 2, remaining)
            w.writeframes(b"\x00\x00" * n)
            remaining -= n


def _wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return None


def _media_duration(path: Path, app_root: Path) -> float | None:
    if not path or not path.exists():
        return None
    if path.suffix.lower() == ".wav":
        d = _wav_duration(path)
        if d:
            return d
    try:
        probe = _ffprobe_exe(app_root)
        if not probe:
            return None
        proc = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode == 0:
            return float(proc.stdout.strip())
    except Exception:
        return None
    return None


def _is_image(p: Path | None) -> bool:
    return bool(p and p.exists() and p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def _is_audio(p: Path | None) -> bool:
    return bool(p and p.exists() and p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _static_vf() -> str:
    return "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p"


def _ken_burns_vf(motion: str, duration: float) -> str:
    frames = max(30, int(float(duration or 1) * 30))
    # zoompan understands `on`; crop does not. V33 keeps all motion inside zoompan.
    if motion == "pan_left":
        zp = f"zoompan=z='1.08':x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30"
    elif motion == "pan_right":
        zp = f"zoompan=z='1.08':x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30"
    elif motion == "push_out":
        zp = "zoompan=z='max(1.08-on*0.0007,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30"
    else:
        zp = "zoompan=z='min(1+on*0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30"
    return "scale=2400:1350:force_original_aspect_ratio=increase," + zp + ",format=yuv420p"


class V33Renderer:
    """V33: real media render preview.

    Differences from V32:
    - Reads real approved visual-slot images when present.
    - Reads real approved block narration when present and uses actual audio duration.
    - Reads scene-level music when present and ducks/mixes it under speech.
    - Adds safe Ken Burns camera motion with automatic static-filter fallback.
    - Writes richer diagnostics and render reports.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.app_root = _project_root_from_project_dir(self.root)
        self.production = self.root / "production"
        self.exports = self.root / "exports"
        self.render_root = self.root / "renders" / "v33"
        self.fallback_root = self.root / "assets" / "render_fallbacks"
        self.visuals = VisualSlotManager(db)
        self.scene_music = SceneMusicManager(db)

    def prepare_render_environment(self, visual_slots: int = 15) -> dict:
        self.production.mkdir(parents=True, exist_ok=True)
        self.exports.mkdir(parents=True, exist_ok=True)
        self.render_root.mkdir(parents=True, exist_ok=True)
        self.fallback_root.mkdir(parents=True, exist_ok=True)

        normalize_project_assets(self.db, visual_slots=visual_slots, create_placeholders=True)
        timeline = build_timeline(self.db)
        build_v31_timeline_preview(self.db, visual_slots=visual_slots)

        default_image = self.fallback_root / "default_visual_1920x1080.bmp"
        if not default_image.exists():
            _bmp_24(default_image, seed=1)

        # Ensure every planned slot has a usable fallback BMP.
        slots = self.visuals.load_plan().get("slots", [])
        for i, slot in enumerate(slots, 1):
            sid = slot.get("id") or f"VIS{i:03d}"
            fallback = self.fallback_root / "visual_slots" / sid / "fallback.bmp"
            if not fallback.exists():
                _bmp_24(fallback, seed=i)

        return {
            "version": "v33_render_environment",
            "timeline_blocks": timeline.get("total_blocks", 0),
            "runtime_minutes": timeline.get("runtime_minutes", 0),
            "ffmpeg": _ffmpeg_exe(self.app_root),
            "default_image": _rel(self.root, default_image),
            "policy": {
                "visuals": "approved visual slot image, otherwise slot fallback bmp",
                "voice": "approved block voice and real duration, otherwise silence",
                "scene_music": "approved scene music mixed quietly under narration when available",
                "camera": "Ken Burns with safe static fallback on FFmpeg failure",
            },
        }

    def _resolve_visual(self, block: dict) -> tuple[Path, bool, str]:
        # 1. Timeline path, if it is a real image.
        p = _abs(self.root, block.get("visual_path"))
        if _is_image(p):
            return p, False, "timeline_visual_path"

        # 2. Current approved slot asset from the slot folder.
        sid = block.get("visual_slot_id") or "VIS001"
        approved = self.visuals.find_approved_slot_asset(sid)
        if _is_image(approved):
            return approved, False, "visual_slot_approved"

        # 3. Fallback BMP per slot.
        fallback = self.fallback_root / "visual_slots" / sid / "fallback.bmp"
        if not fallback.exists():
            _bmp_24(fallback, seed=sum(ord(c) for c in sid) % 97)
        return fallback, True, "fallback_visual"

    def _resolve_voice(self, block: dict, timeline_duration: float) -> tuple[Path, bool, float, str]:
        p = _abs(self.root, block.get("voice_path"))
        if _is_audio(p):
            d = _media_duration(p, self.app_root) or timeline_duration
            return p, False, max(0.5, float(d)), "approved_voice"

        fallback = self.fallback_root / "silence" / f"{block.get('block_id','block')}_{int(timeline_duration)}s.wav"
        if not fallback.exists():
            _silence_wav(fallback, timeline_duration)
        return fallback, True, max(0.5, float(timeline_duration or 1)), "fallback_silence"

    def _resolve_music(self, block: dict) -> tuple[Path | None, bool, str]:
        p = _abs(self.root, block.get("scene_music_path"))
        if _is_audio(p):
            return p, False, "timeline_scene_music"
        sid = block.get("scene_music_id") or block.get("scene_id") or ""
        approved = self.scene_music.find_approved_scene_asset(sid) if sid else None
        if _is_audio(approved):
            return approved, False, "scene_music_approved"
        return None, True, "no_real_scene_music"

    def _block_command(self, image: Path, voice: Path, out: Path, duration: float, motion: str = "slow_zoom", music: Path | None = None, safe_static: bool = False) -> list[str]:
        duration = max(0.5, float(duration or 1.0))
        vf = _static_vf() if safe_static else _ken_burns_vf(motion, duration)
        ffmpeg = _ffmpeg_exe(self.app_root)

        cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(image), "-i", str(voice)]
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music)]
            fc = (
                f"[0:v]{vf}[v];"
                f"[1:a]volume=1.0[a0];"
                f"[2:a]volume=0.18,atrim=0:{duration:.3f},asetpts=N/SR/TB[a1];"
                f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=1[a]"
            )
            cmd += [
                "-t", f"{duration:.3f}",
                "-filter_complex", fc,
                "-map", "[v]", "-map", "[a]",
            ]
        else:
            cmd += [
                "-t", f"{duration:.3f}",
                "-vf", vf,
                "-map", "0:v", "-map", "1:a",
            ]

        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(out),
        ]
        return cmd

    def _run_ffmpeg_with_fallback(self, job: dict, out: Path, preview_dir: Path) -> tuple[bool, str]:
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = self._block_command(
            Path(job["image_abs"]),
            Path(job["voice_abs"]),
            out,
            job["duration_seconds"],
            job.get("motion", "slow_zoom"),
            Path(job["music_abs"]) if job.get("music_abs") else None,
            safe_static=False,
        )
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            return True, "ken_burns"

        # Save the motion failure and retry with static filter. This keeps production moving.
        fail_log = preview_dir / f"{job['block_id']}_motion_ffmpeg_error.log"
        fail_log.write_text("COMMAND:\n" + "\n".join(cmd) + "\n\nSTDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="ignore")

        cmd2 = self._block_command(
            Path(job["image_abs"]),
            Path(job["voice_abs"]),
            out,
            job["duration_seconds"],
            job.get("motion", "slow_zoom"),
            Path(job["music_abs"]) if job.get("music_abs") else None,
            safe_static=True,
        )
        proc2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc2.returncode == 0:
            return True, "static_fallback"

        log = preview_dir / f"{job['block_id']}_ffmpeg_error.log"
        log.write_text("COMMAND:\n" + "\n".join(cmd2) + "\n\nSTDOUT:\n" + proc2.stdout + "\n\nSTDERR:\n" + proc2.stderr, encoding="utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg failed on {job['block_id']}. Log: {log}")

    def _jobs_from_timeline(self) -> tuple[dict, list[dict]]:
        timeline = json.loads((self.production / "timeline.json").read_text(encoding="utf-8"))
        blocks = timeline.get("blocks", [])
        jobs: list[dict] = []
        motions = ["slow_zoom", "pan_left", "slow_zoom", "pan_right", "push_out"]
        for i, b in enumerate(blocks, 1):
            bid = b.get("block_id") or f"block_{i:04d}"
            timeline_duration = float(b.get("duration_seconds") or 1)
            image, image_fallback, image_source = self._resolve_visual(b)
            voice, voice_fallback, actual_duration, voice_source = self._resolve_voice(b, timeline_duration)
            music, music_missing, music_source = self._resolve_music(b)
            out = self.render_root / "blocks" / f"{bid}.mp4"
            jobs.append({
                "block_id": bid,
                "scene_id": b.get("scene_id", ""),
                "character": b.get("character", ""),
                "duration_seconds": round(actual_duration, 3),
                "timeline_duration_seconds": timeline_duration,
                "image": _rel(self.root, image),
                "image_abs": str(image),
                "image_source": image_source,
                "voice": _rel(self.root, voice),
                "voice_abs": str(voice),
                "voice_source": voice_source,
                "music": _rel(self.root, music) if music else "",
                "music_abs": str(music) if music else "",
                "music_source": music_source,
                "output": _rel(self.root, out),
                "output_abs": str(out),
                "motion": motions[(i - 1) % len(motions)],
                "used_fallback_visual": image_fallback,
                "used_fallback_voice": voice_fallback,
                "used_real_music": bool(music and not music_missing),
                "ready_for_final": (not image_fallback and not voice_fallback),
            })
        return timeline, jobs

    def build_render_package(self, visual_slots: int = 15) -> dict:
        env = self.prepare_render_environment(visual_slots=visual_slots)
        try:
            build_v31_production_package(self.db, visual_slots=visual_slots)
        except Exception:
            pass

        timeline, jobs = self._jobs_from_timeline()
        render_dir = self.exports / "v33_render"
        render_dir.mkdir(parents=True, exist_ok=True)
        (self.render_root / "blocks").mkdir(parents=True, exist_ok=True)

        manifest = {
            "version": "v33_real_media_render_package",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "environment": env,
            "total_blocks": len(jobs),
            "runtime_minutes_estimated": timeline.get("runtime_minutes"),
            "runtime_minutes_actual_audio_based": round(sum(j["duration_seconds"] for j in jobs) / 60, 2),
            "coverage": {
                "real_voice_blocks": sum(1 for j in jobs if not j["used_fallback_voice"]),
                "real_visual_blocks": sum(1 for j in jobs if not j["used_fallback_visual"]),
                "real_music_blocks": sum(1 for j in jobs if j["used_real_music"]),
                "final_ready_blocks": sum(1 for j in jobs if j["ready_for_final"]),
            },
            "block_jobs": jobs,
        }
        manifest_path = render_dir / "v33_render_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        csv_path = render_dir / "v33_render_jobs.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            fields = ["block_id", "scene_id", "duration_seconds", "image", "image_source", "voice", "voice_source", "music", "music_source", "output", "motion", "used_fallback_visual", "used_fallback_voice", "used_real_music", "ready_for_final"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for j in jobs:
                writer.writerow({k: j.get(k, "") for k in fields})

        readme = render_dir / "README_V33_RENDER.md"
        readme.write_text(
            "# Histora V33 Render Package\n\n"
            "V33 renders actual media where available:\n"
            "- approved visual-slot images from `assets/visual_slots/VISxxx/approved.png`\n"
            "- approved narration WAV/MP3 per block\n"
            "- approved scene music from `assets/scene_music/Sxxx/approved.mp3`\n\n"
            "If an asset is missing, V33 uses a safe fallback so rendering can still be tested.\n"
            "The app button **Render V33 Test MP4** renders a short preview immediately.\n",
            encoding="utf-8",
        )

        report = {
            "version": "v33_render_package_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "manifest": str(manifest_path),
            "csv": str(csv_path),
            "readme": str(readme),
            "total_blocks": len(jobs),
            "coverage": manifest["coverage"],
            "render_dir": str(render_dir),
        }
        report_path = self.production / "v33_report_latest.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def render_test_mp4(self, block_limit: int = 3, visual_slots: int = 15, progress=None) -> dict:
        self.build_render_package(visual_slots=visual_slots)
        manifest_path = self.exports / "v33_render" / "v33_render_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jobs = manifest.get("block_jobs", [])[:max(1, int(block_limit or 3))]
        preview_dir = self.exports / "v33_preview"
        blocks_dir = preview_dir / "blocks"
        preview_dir.mkdir(parents=True, exist_ok=True)
        blocks_dir.mkdir(parents=True, exist_ok=True)

        rendered = []
        render_modes: list[dict] = []
        total = len(jobs) + 1
        for i, j in enumerate(jobs, 1):
            if progress:
                progress("render_block", j["block_id"], i, total)
            out = blocks_dir / f"{j['block_id']}.mp4"
            ok, mode = self._run_ffmpeg_with_fallback(j, out, preview_dir)
            if ok:
                rendered.append(out)
                render_modes.append({"block_id": j["block_id"], "mode": mode, "motion": j.get("motion"), "duration": j.get("duration_seconds")})

        concat = preview_dir / "concat.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in rendered), encoding="utf-8")
        output = preview_dir / f"preview_v33_first_{len(rendered)}_blocks.mp4"
        if progress:
            progress("concat", output.name, total, total)
        proc = subprocess.run([_ffmpeg_exe(self.app_root), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            log = preview_dir / "concat_ffmpeg_error.log"
            log.write_text(proc.stdout + "\n\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg concat failed. Log: {log}")

        report = {
            "version": "v33_test_render",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "blocks_rendered": len(rendered),
            "output": str(output),
            "rendered_blocks": [str(p) for p in rendered],
            "render_modes": render_modes,
            "coverage": manifest.get("coverage", {}),
        }
        report_path = preview_dir / "test_render_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report


def build_v33_render_package(db, visual_slots: int = 15) -> dict:
    return V33Renderer(db).build_render_package(visual_slots=visual_slots)


def render_v33_test_mp4(db, block_limit: int = 3, visual_slots: int = 15, progress=None) -> dict:
    return V33Renderer(db).render_test_mp4(block_limit=block_limit, visual_slots=visual_slots, progress=progress)
