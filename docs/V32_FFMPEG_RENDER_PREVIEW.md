# V32 FFmpeg Render Preview

V32 adds the first actual MP4 rendering layer.

## New toolbar actions

- **Build V32 Render**: prepares an FFmpeg-ready render package without running the full render.
- **Render Test MP4**: renders the first N blocks into a real MP4 using FFmpeg.

## Output

```text
assets/render_fallbacks/
exports/v32_render/v32_render_manifest.json
exports/v32_render/v32_render_jobs.csv
exports/v32_render/render_all_blocks.bat
exports/v32_render/concat_episode.bat
exports/v32_preview/preview_first_N_blocks.mp4
production/v32_report_latest.json
```

## Policy

- Approved real images are used when available.
- TXT placeholders are replaced by generated BMP fallback images.
- Missing voices are replaced by silence for preview rendering.
- Full episode rendering is generated as BAT scripts so the user can run it outside the UI.
