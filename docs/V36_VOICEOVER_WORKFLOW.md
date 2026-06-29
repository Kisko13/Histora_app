# Histora V36 — Voiceover Workflow

V36 adds a voiceover production layer on top of the working V34/V35 pipeline.

## Main idea

- Qwen is treated as the primary provider in the app UI.
- Backup providers are used in order when the primary fails.
- Default chain: `qwen,mock`.
- Configure with `.env`:

```env
V36_PRIMARY_VOICE_PROVIDER=qwen
V36_BACKUP_VOICE_PROVIDERS=mock
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
```

Important: local Ollama/Qwen is normally a text model. It can help with voice planning, tags, and prompts. It only creates audio if your project already has a `qwen` synth provider implemented. If not, V36 falls back to mock or another configured provider.

## Test order

1. Run studio.
2. Click **Voiceover Plan**.
3. Check dashboard and Qwen/Ollama status.
4. Click **Generate Voice Queue**.
5. Use provider chain `qwen,mock`.
6. Use `3` blocks for first test.
7. Open review queue.

## Generated files

```text
production/v36_voiceover_plan_latest.json
exports/v36_voiceover/voiceover_dashboard.html
exports/v36_voiceover/voice_review_queue.html
exports/v36_voiceover/voiceover_queue.csv
exports/v36_voiceover/voice_generation_report_latest.json
```
