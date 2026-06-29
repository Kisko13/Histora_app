# V30 Assembly Package

V30 converts the V29 timeline architecture into an editing-ready production package.

Adds:

1. Camera movement plan
- `production/camera_plan.json`
- deterministic Ken Burns / pan / zoom metadata for every block

2. Subtitles
- `exports/subtitles/captions.srt`
- `exports/subtitles/captions.vtt`
- `exports/subtitles/captions.ass`
- `exports/subtitles/captions.json`

3. CapCut/manual import package
- `exports/capcut_v30/timeline_import_plan.csv`
- `exports/capcut_v30/README_IMPORT_ORDER.txt`
- `exports/capcut_v30/capcut_package_manifest.json`

4. Episode export package
- `exports/episode_v30_package/`
- includes copied timeline, camera, subtitle, and import files

5. V30 health
- extends health report with camera/subtitle/package status

Test order:

1. Plan Visual/Music
2. Generate Missing Assets
3. Build Timeline
4. Health
5. Build Package

V30 still does not render final MP4. It creates the final editing/assembly package and prepares the architecture for FFmpeg/native rendering.
