# Historical POV Studio — v9 Changes

## What's new (the 5 milestones from the roadmap)

### 1. Qwen API "Test Connection" button
- `Qwen Voice Lab` tab → **🔌 Test Connection**
- Checks config keys exist, then sends a live ping to the Qwen REST endpoint
- Shows ✅ green / ❌ red status with the HTTP response code
- API call runs in a background thread — UI never freezes

### 2. Real WAV generation
- `qwen_client.py` completely rewritten
- Handles all three Qwen response shapes: base64 `output.audio.data`, `output.audio_url` download, and raw `audio/wav` body
- Saves a `.response.json` sidecar for debugging
- Raises a clear error if 200 OK is returned but audio bytes aren't found

### 3. Embedded audio player
- New `AudioPlayer` widget (PySide6 `QMediaPlayer`) embedded directly in **Block Workspace**
- Play / Pause / Stop / seek slider / time counter — no external app
- Auto-loads the latest audio version when you select a block
- Click any row in the version list to load that specific version
- Also embedded in **Qwen Voice Lab** for test audio playback

### 4. Save generated audio as version 1
- ⚡ **Generate Voice** button added directly in Block Workspace
- Generates audio for the currently selected block only (single-block workflow)
- Result is saved to `audio_versions` table and immediately loaded into the player
- Full batch Build still available via toolbar

### 5. Approve / Redo workflow
- ✓ **Approve Voice** copies latest raw audio → `assets/audio_final/`
- ↻ **Redo Voice** sets status back to `redo` with a reason
- ✕ **Reject** marks block rejected
- All three update the status badge instantly

## Files changed
- `hps/providers/voice/qwen_client.py` — real WAV decoding + live connection test
- `hps_qt/widgets/audio_player.py` — new embedded player widget
- `hps_qt/widgets/block_workspace.py` — player, version list, generate button
- `hps_qt/widgets/qwen_voice_lab.py` — threaded API calls, inline player, connection test
- `studio_qt.py` — wired `generate_block_clicked`, pass `db_root` to workspace
