# V29 Timeline Assembly Engine

V29 changes Histora from block image/music management into the final production architecture:

- Voice remains block-based.
- Images are visual-slot based.
- Music is scene-based.
- Assembly is driven by `production/timeline.json`.

## New files generated during testing

- `production/timeline.json`
- `production/health_report_latest.json`
- `production/assembly_report_latest.json`
- `assets/visual_slots/VIS001/metadata.json`
- `assets/scene_music/S001/metadata.json`
- `renders/blocks/B0001.txt`
- `renders/scenes/S001.txt`
- `exports/episode_v29_manifest.txt`

## Buttons

### Plan Visual/Music
Creates or updates visual-slot and scene-music plans.

### Build Timeline
Creates `production/timeline.json` from voice files, visual slots, and scene music.

### Health
Shows production readiness: voice, visual slots, scene music, timeline, assembly, export.

### Generate Missing Assets
Runs the V28/V29 production policy:
- generate selected missing voices
- generate visual slot placeholders
- generate scene music placeholders

### Build
Runs the V29 timeline assembly engine.
For now it creates resume-safe manifests/placeholders, not final MP4 rendering.
This is intentional so the whole workflow can be tested without FFmpeg or real media.

## Next future step
Replace the placeholder manifests with FFmpeg render commands while keeping the same timeline and asset manager architecture.
