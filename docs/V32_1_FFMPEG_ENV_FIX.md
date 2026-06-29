# V32.1 FFmpeg Env Fix

Renderer now resolves FFmpeg in this order:

1. OS environment variable `FFMPEG_EXE`
2. project `.env` line `FFMPEG_EXE=C:\...\ffmpeg.exe`
3. bundled app paths `ffmpeg/bin/ffmpeg.exe`, `tools/ffmpeg/bin/ffmpeg.exe`, `bin/ffmpeg.exe`
4. system PATH

This removes dependency on Windows PATH for rendering.
