# V33 Real Media Render

V33 replaces placeholder-only rendering with real media where available.

Adds:

- approved visual-slot image loading from `assets/visual_slots/VISxxx/approved.png`
- approved narration loading per block
- real audio duration detection for WAV/MP3 where ffprobe is available
- scene-level music mixing under narration when `assets/scene_music/Sxxx/approved.mp3` exists
- Ken Burns camera movement
- automatic static-filter fallback if FFmpeg motion filter fails
- richer render package and test render reports

Test:

1. Run `Build V33 Render`.
2. Run `Render V33 Test MP4`.
3. Use 3 blocks first.
4. To test real visuals, put a PNG at `projects/cannae_001/assets/visual_slots/VIS001/approved.png` and render again.
