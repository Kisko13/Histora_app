"""
Assembly Engine — V23
Turns approved assets into a real episode timeline.
Reads voice + image + music → builds timeline clips → exports assembly package.
"""

import csv
import json
import shutil
import wave
from pathlib import Path

from hps.core.block_state import compute_block_state, approved_voice_path, approved_image_path, approved_music_path


class AssemblyEngine:
    def __init__(self, db):
        self.db = db
        self.out_dir = db.root_dir / "exports" / "assembly_engine"

    # ------------------------------------------------------------------ #
    #  Duration helpers
    # ------------------------------------------------------------------ #

    def _wav_duration(self, path: Path) -> float:
        """Exact duration from a real WAV file."""
        try:
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return 0.0

    def _text_duration(self, text: str) -> float:
        """Estimate duration from mock .txt voice file content."""
        return max(3.0, len(text) / 13.0)

    def _get_duration(self, voice_path, text: str) -> float:
        """Return best available duration for a block."""
        if voice_path is None:
            return self._text_duration(text)
        path = Path(voice_path) if not isinstance(voice_path, Path) else voice_path
        if path.suffix.lower() == ".wav":
            d = self._wav_duration(path)
            return d if d > 0 else self._text_duration(text)
        if path.suffix.lower() in (".txt",):
            try:
                return self._text_duration(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                return self._text_duration(text)
        # mp3 / m4a — fall back to text estimate until mutagen is available
        return self._text_duration(text)

    # ------------------------------------------------------------------ #
    #  Core: build timeline
    # ------------------------------------------------------------------ #

    def build_timeline(self) -> list:
        """
        Build an ordered list of timeline items, one per block.
        Each item contains all timing and asset path info.
        """
        blocks = self.db.blocks()
        timeline = []
        cursor = 0.0

        for seq, block in enumerate(blocks, start=1):
            block_id = block["id"]
            text = (block["text"] or "").strip()

            # Resolve approved asset paths
            voice = approved_voice_path(self.db, block_id)
            image = approved_image_path(self.db, block_id)
            music = approved_music_path(self.db, block_id)

            duration = self._get_duration(voice, text)

            is_real_audio = voice is not None and Path(voice).suffix.lower() in (".wav", ".mp3", ".m4a", ".aac", ".flac")
            missing = []
            if not voice:
                missing.append("voice")
            if not image:
                missing.append("image")
            if not music:
                missing.append("music")

            ready = bool(voice and image)      # assembly-ready: voice + image
            complete = bool(voice and image and music)

            def rel(p):
                if p is None:
                    return ""
                try:
                    return str(Path(p).relative_to(self.db.root_dir)).replace("\\", "/")
                except ValueError:
                    return str(p).replace("\\", "/")

            item = {
                "sequence": seq,
                "block_id": block_id,
                "scene": block["scene_title"],
                "character": block["character_id"] if "character_id" in block.keys() else "",
                "text": text[:200] + ("…" if len(text) > 200 else ""),
                "start_seconds": round(cursor, 3),
                "duration_seconds": round(duration, 3),
                "end_seconds": round(cursor + duration, 3),
                "voice": rel(voice),
                "voice_is_real_audio": is_real_audio,
                "image": rel(image),
                "music": rel(music),
                "ready": ready,
                "complete": complete,
                "missing": missing,
            }
            timeline.append(item)
            cursor += duration

        return timeline

    # ------------------------------------------------------------------ #
    #  Exports
    # ------------------------------------------------------------------ #

    def export_timeline_json(self, timeline: list) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "timeline.json"
        path.write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def export_timeline_csv(self, timeline: list) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "timeline.csv"
        if not timeline:
            path.write_text("", encoding="utf-8")
            return path
        fields = list(timeline[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for item in timeline:
                row = dict(item)
                row["missing"] = "|".join(row["missing"])
                w.writerow(row)
        return path

    def export_preview_html(self, timeline: list) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "preview.html"

        total_duration = timeline[-1]["end_seconds"] if timeline else 0.0

        rows_html = ""
        for item in timeline:
            ready_badge = (
                '<span style="color:#2ecc71;font-weight:bold">✔ READY</span>'
                if item["ready"]
                else '<span style="color:#e74c3c;font-weight:bold">✘ NOT READY</span>'
            )
            complete_badge = (
                '<span style="color:#27ae60;font-weight:bold">✔ COMPLETE</span>'
                if item["complete"]
                else '<span style="color:#e67e22">○ PARTIAL</span>'
            )
            missing_str = ", ".join(item["missing"]) if item["missing"] else "—"

            # Image preview
            img_html = ""
            if item["image"]:
                abs_img = self.db.root_dir / item["image"]
                img_html = f'<img src="{abs_img.as_posix()}" style="max-width:120px;max-height:80px;border-radius:4px;">'

            # Audio player
            audio_html = ""
            if item["voice"] and item["voice_is_real_audio"]:
                abs_voice = self.db.root_dir / item["voice"]
                audio_html = f'<audio controls style="height:28px;width:180px;"><source src="{abs_voice.as_posix()}"></audio>'
            elif item["voice"]:
                audio_html = '<span style="color:#888;font-size:0.85em">mock .txt</span>'

            # Music player
            music_html = ""
            if item["music"]:
                abs_music = self.db.root_dir / item["music"]
                music_html = f'<audio controls style="height:28px;width:160px;"><source src="{abs_music.as_posix()}"></audio>'

            rows_html += f"""
            <tr>
              <td style="text-align:center">{item['sequence']}</td>
              <td><b>{item['block_id']}</b></td>
              <td>{item['scene']}</td>
              <td>{item['character']}</td>
              <td>{ready_badge}</td>
              <td>{complete_badge}</td>
              <td>{item['start_seconds']:.1f}s</td>
              <td>{item['duration_seconds']:.1f}s</td>
              <td>{img_html}</td>
              <td>{audio_html}</td>
              <td>{music_html}</td>
              <td style="color:#e74c3c">{missing_str}</td>
              <td style="font-size:0.8em;max-width:220px;overflow:hidden">{item['text']}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Episode Preview — Assembly Engine</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ color: #e94560; margin-bottom: 4px; }}
  .meta {{ color: #aaa; margin-bottom: 20px; font-size: 0.9em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.88em; }}
  th {{ background: #16213e; color: #e94560; padding: 10px 8px; text-align: left; position: sticky; top: 0; }}
  td {{ padding: 8px; border-bottom: 1px solid #2a2a4a; vertical-align: middle; }}
  tr:hover td {{ background: #1e2a4a; }}
  .legend {{ margin: 12px 0; font-size: 0.85em; color: #aaa; }}
</style>
</head>
<body>
<h1>📽 Episode Preview</h1>
<div class="meta">
  Total blocks: {len(timeline)} &nbsp;|&nbsp;
  Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min) &nbsp;|&nbsp;
  Ready blocks: {sum(1 for i in timeline if i['ready'])} &nbsp;|&nbsp;
  Complete blocks: {sum(1 for i in timeline if i['complete'])}
</div>
<div class="legend">
  <b>READY</b> = voice + image present &nbsp;|&nbsp;
  <b>COMPLETE</b> = voice + image + music present
</div>
<table>
  <thead>
    <tr>
      <th>#</th><th>Block</th><th>Scene</th><th>Character</th>
      <th>Ready</th><th>Complete</th>
      <th>Start</th><th>Duration</th>
      <th>Image</th><th>Voice</th><th>Music</th>
      <th>Missing</th><th>Script excerpt</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</body>
</html>"""
        path.write_text(html, encoding="utf-8")
        return path

    def package_assets(self, timeline: list) -> Path:
        """Copy approved assets into exports/assembly_engine/package/"""
        pkg = self.out_dir / "package"
        for subdir in ("voice", "image", "music"):
            (pkg / subdir).mkdir(parents=True, exist_ok=True)

        manifest = []
        for item in timeline:
            entry = {"block_id": item["block_id"], "sequence": item["sequence"]}
            for asset_key, subdir in [("voice", "voice"), ("image", "image"), ("music", "music")]:
                rel = item[asset_key]
                if rel:
                    src = self.db.root_dir / rel
                    dst = pkg / subdir / src.name
                    try:
                        shutil.copy2(src, dst)
                        entry[asset_key] = str(dst.relative_to(self.out_dir)).replace("\\", "/")
                    except Exception as e:
                        entry[asset_key] = f"ERROR: {e}"
                else:
                    entry[asset_key] = ""
            manifest.append(entry)

        manifest_path = self.out_dir / "packaged_assets.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path

    def export_ffmpeg_script(self, timeline: list) -> Path:
        """Generate a Windows .bat FFmpeg render script."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "render_episode_ffmpeg.bat"

        lines = [
            "@echo off",
            "REM ============================================================",
            "REM  Historical POV Studio — Episode Render Script (V23)",
            f"REM  Blocks: {len(timeline)}",
            "REM ============================================================",
            "",
            "cd /d %~dp0",
            "if not exist render_parts mkdir render_parts",
            "",
        ]

        concat_entries = []
        for item in timeline:
            if not item["ready"] or not item["voice_is_real_audio"]:
                lines.append(f"REM  SKIP {item['block_id']} — {'not ready' if not item['ready'] else 'mock voice'}")
                continue

            block_id = item["block_id"]
            voice_abs = (self.db.root_dir / item["voice"]).as_posix().replace("/", "\\")
            image_abs = (self.db.root_dir / item["image"]).as_posix().replace("/", "\\")
            out_clip = f"render_parts\\{block_id}.mp4"

            lines += [
                f"",
                f"REM  Block {block_id} — {item['scene']}",
                f"echo Rendering {block_id}...",
                f'ffmpeg -y -loop 1 -i "{image_abs}" -i "{voice_abs}" ^',
                f'  -c:v libx264 -tune stillimage -c:a aac -b:a 192k ^',
                f'  -pix_fmt yuv420p -shortest ^',
                f'  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" ^',
                f'  {out_clip}',
                f"if errorlevel 1 echo WARNING: {block_id} render failed",
                "",
            ]
            concat_entries.append(out_clip)

        # Write concat list
        if concat_entries:
            concat_list = self.out_dir / "concat_list.txt"
            concat_lines = [f"file '{e}'" for e in concat_entries]
            concat_list.write_text("\n".join(concat_lines), encoding="utf-8")

            lines += [
                "",
                "REM  === Concatenate all clips ===",
                "echo Concatenating clips...",
                'ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy episode_preview.mp4',
                "echo Done! Output: episode_preview.mp4",
            ]
        else:
            lines += [
                "",
                "echo No ready clips to render. Generate and approve voice + image assets first.",
            ]

        path.write_text("\r\n".join(lines), encoding="utf-8")
        return path

    def _export_summary(self, timeline: list) -> Path:
        """Write assembly_summary.json."""
        ready = [i for i in timeline if i["ready"]]
        complete = [i for i in timeline if i["complete"]]
        total_dur = timeline[-1]["end_seconds"] if timeline else 0.0
        summary = {
            "total_blocks": len(timeline),
            "ready_blocks": len(ready),
            "complete_blocks": len(complete),
            "total_duration_seconds": round(total_dur, 2),
            "total_duration_minutes": round(total_dur / 60, 2),
            "missing_voice": sum(1 for i in timeline if "voice" in i["missing"]),
            "missing_image": sum(1 for i in timeline if "image" in i["missing"]),
            "missing_music": sum(1 for i in timeline if "music" in i["missing"]),
        }
        p = self.out_dir / "assembly_summary.json"
        p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return p

    # ------------------------------------------------------------------ #
    #  build_all — main entry point
    # ------------------------------------------------------------------ #

    def build_all(self) -> dict:
        """
        Run the full assembly pipeline.
        Returns a dict with paths to all generated files and the timeline.
        """
        self.out_dir.mkdir(parents=True, exist_ok=True)
        timeline = self.build_timeline()

        return {
            "timeline": timeline,
            "timeline_json": self.export_timeline_json(timeline),
            "timeline_csv": self.export_timeline_csv(timeline),
            "preview_html": self.export_preview_html(timeline),
            "packaged_assets": self.package_assets(timeline),
            "ffmpeg_script": self.export_ffmpeg_script(timeline),
            "summary": self._export_summary(timeline),
            "out_dir": self.out_dir,
        }
