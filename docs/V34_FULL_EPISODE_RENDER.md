# Histora V34 — Full Episode Renderer

V34 turns the proven V33 preview renderer into a resumable episode renderer.

## Adds

- Build V34 Package
- Render V34 Episode
- renders all block MP4s into `exports/v34_full_episode/blocks/`
- skips existing rendered blocks when resume is enabled
- stops on first failed block so you can fix and resume
- concatenates rendered blocks into one MP4
- writes per-block status reports and FFmpeg logs
- copy-concat first, re-encode fallback if concat copy fails

## Test order

1. Run `run_studio_v24.bat`
2. Click `Build V34 Package`
3. Click `Render V34 Episode`
4. Enter `5` or `10` first
5. If that works, run again with `0` for full episode

## Expected files

- `exports/v34_full_episode/v34_full_episode_manifest.json`
- `exports/v34_full_episode/blocks/*.mp4`
- `exports/v34_full_episode/episode_v34_test.mp4` for limited test
- `exports/v34_full_episode/episode_v34_full.mp4` for full render
- `exports/v34_full_episode/v34_full_episode_render_report.json`
- `production/v34_report_latest.json`

## Notes

V34 uses real approved assets when available and safe fallbacks when missing.
The goal is production continuity: render, resume, inspect logs, continue.
