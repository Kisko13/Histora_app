
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import struct
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.v29_asset_managers import project_dir
from hps.core.v29_timeline_engine import build_timeline
from hps.core.v31_asset_library import normalize_project_assets
from hps.core.v31_timeline_preview import build_v31_timeline_preview
from hps.core.v31_assembly_package import build_v31_production_package


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
    if p.is_absolute():
        return p
    return root / p


def _q(p: Path | str) -> str:
    """Windows-batch safe path quoting."""
    return '"' + str(p).replace('"', '') + '"'


def _fmt(seconds: float | int) -> str:
    seconds = int(seconds or 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _bmp_24(path: Path, width: int = 1920, height: int = 1080, seed: int = 0):
    """Create a simple 24-bit BMP placeholder using only the Python stdlib."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row_pad = (4 - (width * 3) % 4) % 4
    row_size = width * 3 + row_pad
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    # muted historical palette with slight vertical gradient
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


def _project_root_from_project_dir(project_root: Path) -> Path:
    """project_root is usually .../projects/cannae_001. App root is two levels up."""
    try:
        return project_root.parents[1]
    except Exception:
        return Path.cwd()


def _read_env_file(app_root: Path) -> dict[str, str]:
    """Tiny .env reader so we do not depend on python-dotenv."""
    env = {}
    for candidate in [app_root / ".env", Path.cwd() / ".env"]:
        if not candidate.exists():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env


def _ffmpeg_candidates(app_root: Path | None = None) -> list[str]:
    app_root = app_root or Path.cwd()
    env_file = _read_env_file(app_root)
    candidates = []

    # 1) explicit Windows/session env
    if os.environ.get("FFMPEG_EXE"):
        candidates.append(os.environ["FFMPEG_EXE"])

    # 2) project .env
    if env_file.get("FFMPEG_EXE"):
        candidates.append(env_file["FFMPEG_EXE"])

    # 3) bundled portable ffmpeg inside app folder
    candidates += [
        str(app_root / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(app_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(app_root / "bin" / "ffmpeg.exe"),
    ]

    # 4) PATH fallback
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    # de-dupe, preserving order
    out = []
    seen = set()
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
        # allow PATH executable names on non-Windows or if shutil found it
        if c.lower() == "ffmpeg" or shutil.which(c):
            return c
    checked = "\n".join(_ffmpeg_candidates(app_root)) or "No candidates."
    raise RuntimeError(
        "FFmpeg not found. Set FFMPEG_EXE in .env to the full ffmpeg.exe path.\n\n"
        f"Checked:\n{checked}"
    )


class V32Renderer:
    """Actual render-package layer.

    V32 is the first version that can create real MP4 previews using FFmpeg when it is
    installed. It stays production-safe by generating fallback BMP/silence media for
    missing assets, so the user can test rendering before all real assets are ready.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.production = self.root / "production"
        self.exports = self.root / "exports"
        self.render_root = self.root / "renders" / "v32"
        self.fallback_root = self.root / "assets" / "render_fallbacks"

    def prepare_render_environment(self, visual_slots: int = 15) -> dict:
        self.production.mkdir(parents=True, exist_ok=True)
        self.exports.mkdir(parents=True, exist_ok=True)
        self.render_root.mkdir(parents=True, exist_ok=True)
        self.fallback_root.mkdir(parents=True, exist_ok=True)

        # Ensure previous architecture exists and all plans are normalized.
        normalize_project_assets(self.db, visual_slots=visual_slots, create_placeholders=True)
        timeline = build_timeline(self.db)
        build_v31_timeline_preview(self.db, visual_slots=visual_slots)

        default_image = self.fallback_root / "default_visual_1920x1080.bmp"
        if not default_image.exists():
            _bmp_24(default_image, seed=1)

        # Create per-slot fallback images so the rendered video changes visually even before final art exists.
        slot_fallbacks = []
        visual_plan_path = self.production / "visual_slot_plan.json"
        if visual_plan_path.exists():
            try:
                visual_plan = json.loads(visual_plan_path.read_text(encoding="utf-8"))
                for i, slot in enumerate(visual_plan.get("slots", []), 1):
                    sid = slot.get("id") or f"slot_{i:03d}"
                    p = self.fallback_root / "visual_slots" / sid / "fallback.bmp"
                    if not p.exists():
                        _bmp_24(p, seed=i)
                    slot_fallbacks.append(_rel(self.root, p))
            except Exception:
                pass

        return {
            "version": "v32_render_environment",
            "timeline_blocks": timeline.get("total_blocks", 0),
            "runtime_minutes": timeline.get("runtime_minutes", 0),
            "default_image": _rel(self.root, default_image),
            "slot_fallbacks": slot_fallbacks,
        }

    def _resolve_visual(self, block: dict) -> Path:
        # Prefer real visual path if it is an actual image; fall back if it is a TXT placeholder.
        p = _abs(self.root, block.get("visual_path"))
        if p and p.exists() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return p
        sid = block.get("visual_slot_id") or "slot_001"
        fallback = self.fallback_root / "visual_slots" / sid / "fallback.bmp"
        if not fallback.exists():
            _bmp_24(fallback, seed=sum(ord(c) for c in sid) % 97)
        return fallback

    def _resolve_audio(self, block: dict, duration: float) -> Path:
        p = _abs(self.root, block.get("voice_path"))
        if p and p.exists() and p.suffix.lower() in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
            return p
        fallback = self.fallback_root / "silence" / f"{block.get('block_id','block')}_{int(duration)}s.wav"
        if not fallback.exists():
            _silence_wav(fallback, duration)
        return fallback

    def _block_command(self, image: Path, audio: Path, out: Path, duration: float, motion: str = "slow_zoom") -> list[str]:
        duration = max(0.5, float(duration or 1.0))

        # V32.2 safety fix:
        # Earlier V32 used crop expressions with the variable `on`, but `on` is not
        # available inside the crop filter. It only exists in filters like zoompan.
        # For the production baseline we use a conservative, guaranteed-valid filter.
        # This prioritizes reliable MP4 output over fancy camera motion. Camera motion
        # can be reintroduced later using zoompan-only expressions after render is stable.
        vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p"

        return [
            _ffmpeg_exe(_project_root_from_project_dir(self.root)), "-y",
            "-loop", "1", "-framerate", "30", "-i", str(image),
            "-i", str(audio),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(out),
        ]

    def _write_command_bat(self, path: Path, commands: list[list[str]], title: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["@echo off", f"echo {title}", "echo."]
        for cmd in commands:
            quoted = []
            for part in cmd:
                # keep ffmpeg executable unquoted when it is just 'ffmpeg'
                if part == "ffmpeg" or part.endswith("ffmpeg.exe"):
                    quoted.append(_q(part) if Path(part).suffix else part)
                elif any(ch in str(part) for ch in " &()") or ":\\" in str(part) or "/" in str(part):
                    quoted.append(_q(part))
                else:
                    quoted.append(str(part))
            lines.append(" ".join(quoted))
            lines.append("if errorlevel 1 goto fail")
            lines.append("")
        lines += ["echo.", "echo DONE", "pause", "exit /b 0", ":fail", "echo.", "echo RENDER FAILED", "pause", "exit /b 1"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def build_render_package(self, visual_slots: int = 15) -> dict:
        env = self.prepare_render_environment(visual_slots=visual_slots)
        timeline = json.loads((self.production / "timeline.json").read_text(encoding="utf-8"))
        # Ensure V31 package exists because V32 package builds on it.
        try:
            build_v31_production_package(self.db, visual_slots=visual_slots)
        except Exception:
            pass

        blocks = timeline.get("blocks", [])
        render_dir = self.exports / "v32_render"
        render_dir.mkdir(parents=True, exist_ok=True)
        block_dir = self.render_root / "blocks"
        scene_dir = self.render_root / "scenes"
        block_dir.mkdir(parents=True, exist_ok=True)
        scene_dir.mkdir(parents=True, exist_ok=True)

        block_jobs = []
        for i, b in enumerate(blocks, 1):
            bid = b.get("block_id") or f"block_{i:04d}"
            duration = float(b.get("duration_seconds") or 1)
            image = self._resolve_visual(b)
            audio = self._resolve_audio(b, duration)
            out = block_dir / f"{bid}.mp4"
            motion = ["slow_zoom", "pan_left", "slow_zoom", "pan_right"][i % 4]
            block_jobs.append({
                "block_id": bid,
                "scene_id": b.get("scene_id", ""),
                "duration_seconds": duration,
                "image": _rel(self.root, image),
                "audio": _rel(self.root, audio),
                "output": _rel(self.root, out),
                "motion": motion,
                "ready_for_render": True,
                "source_ready": b.get("ready", False),
                "used_fallback_visual": image.is_relative_to(self.fallback_root) if hasattr(image, 'is_relative_to') else str(image).startswith(str(self.fallback_root)),
                "used_fallback_audio": audio.is_relative_to(self.fallback_root) if hasattr(audio, 'is_relative_to') else str(audio).startswith(str(self.fallback_root)),
            })

        # Write full block render BAT, but do not auto-run it because full 60 min render can be slow.
        commands = []
        for j in block_jobs:
            commands.append(self._block_command(_abs(self.root, j["image"]), _abs(self.root, j["audio"]), _abs(self.root, j["output"]), j["duration_seconds"], j["motion"]))
        full_bat = render_dir / "render_all_blocks.bat"
        self._write_command_bat(full_bat, commands, "Histora V32 - Render all block MP4 files")

        # Concat scripts use generated block MP4s.
        concat_list = render_dir / "concat_blocks.txt"
        concat_list.write_text("".join(f"file '{(self.root / j['output']).as_posix()}'\n" for j in block_jobs), encoding="utf-8")
        episode_mp4 = self.exports / "episode_v32_preview_full.mp4"
        concat_bat = render_dir / "concat_episode.bat"
        self._write_command_bat(concat_bat, [[_ffmpeg_exe(_project_root_from_project_dir(self.root)), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(episode_mp4)]], "Histora V32 - Concatenate rendered blocks")

        render_manifest = {
            "version": "v32_render_package",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "policy": {
                "rendering": "ffmpeg_actual_mp4_supported",
                "voice": "approved voice if available, fallback silence if missing",
                "visuals": "approved image if available, fallback BMP if placeholder/missing",
                "music": "kept in package for CapCut/manual mix; block MP4 preview renders voice+visual first",
            },
            "environment": env,
            "total_blocks": len(block_jobs),
            "runtime_minutes": timeline.get("runtime_minutes"),
            "full_block_render_bat": _rel(self.root, full_bat),
            "concat_bat": _rel(self.root, concat_bat),
            "episode_output": _rel(self.root, episode_mp4),
            "block_jobs": block_jobs,
        }
        manifest_path = render_dir / "v32_render_manifest.json"
        manifest_path.write_text(json.dumps(render_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        csv_path = render_dir / "v32_render_jobs.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["block_id", "scene_id", "duration_seconds", "image", "audio", "output", "motion", "used_fallback_visual", "used_fallback_audio"])
            writer.writeheader()
            for j in block_jobs:
                writer.writerow({k: j.get(k, "") for k in writer.fieldnames})

        readme = render_dir / "README_V32_RENDER.md"
        readme.write_text(
            "# Histora V32 Render Package\n\n"
            "This folder contains real FFmpeg render scripts.\n\n"
            "## Test render inside the app\n"
            "Use the toolbar button **Render Test MP4** and enter 3-10 blocks.\n\n"
            "## Full render manually\n"
            "1. Run `render_all_blocks.bat` to generate block MP4 files.\n"
            "2. Run `concat_episode.bat` to join them into `exports/episode_v32_preview_full.mp4`.\n\n"
            "Missing real images are replaced by BMP placeholders. Missing voices are replaced by silence.\n"
            "This is intentional so you can validate the full timeline before every final asset exists.\n",
            encoding="utf-8",
        )

        report = {
            "version": "v32_render_package_report",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "manifest": str(manifest_path),
            "csv": str(csv_path),
            "readme": str(readme),
            "total_blocks": len(block_jobs),
            "runtime_minutes": timeline.get("runtime_minutes"),
            "render_dir": str(render_dir),
        }
        report_path = self.production / "v32_report_latest.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def render_test_mp4(self, block_limit: int = 3, visual_slots: int = 15, progress=None) -> dict:
        """Run FFmpeg now for a short preview MP4. Safe default: first 3 blocks."""
        self.build_render_package(visual_slots=visual_slots)
        manifest_path = self.exports / "v32_render" / "v32_render_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jobs = manifest.get("block_jobs", [])[:max(1, int(block_limit or 3))]
        preview_dir = self.exports / "v32_preview"
        blocks_dir = preview_dir / "blocks"
        preview_dir.mkdir(parents=True, exist_ok=True)
        blocks_dir.mkdir(parents=True, exist_ok=True)

        rendered = []
        total = len(jobs) + 1
        for i, j in enumerate(jobs, 1):
            if progress:
                progress("render_block", j["block_id"], i, total)
            out = blocks_dir / f"{j['block_id']}.mp4"
            cmd = self._block_command(_abs(self.root, j["image"]), _abs(self.root, j["audio"]), out, j["duration_seconds"], j.get("motion", "slow_zoom"))
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                log = preview_dir / f"{j['block_id']}_ffmpeg_error.log"
                log.write_text(proc.stdout + "\n\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="ignore")
                raise RuntimeError(f"FFmpeg failed on {j['block_id']}. Log: {log}")
            rendered.append(out)

        concat = preview_dir / "concat.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in rendered), encoding="utf-8")
        output = preview_dir / f"preview_first_{len(rendered)}_blocks.mp4"
        if progress:
            progress("concat", output.name, total, total)
        proc = subprocess.run([_ffmpeg_exe(_project_root_from_project_dir(self.root)), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            log = preview_dir / "concat_ffmpeg_error.log"
            log.write_text(proc.stdout + "\n\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg concat failed. Log: {log}")

        report = {
            "version": "v32_test_render",
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "blocks_rendered": len(rendered),
            "output": str(output),
            "rendered_blocks": [str(p) for p in rendered],
        }
        report_path = preview_dir / "test_render_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report


def build_v32_render_package(db, visual_slots: int = 15) -> dict:
    return V32Renderer(db).build_render_package(visual_slots=visual_slots)


def render_v32_test_mp4(db, block_limit: int = 3, visual_slots: int = 15, progress=None) -> dict:
    return V32Renderer(db).render_test_mp4(block_limit=block_limit, visual_slots=visual_slots, progress=progress)
