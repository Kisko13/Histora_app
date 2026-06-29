# Histora V37 — Voice Provider Manager

V37 makes the voice system explicit and production-safe.

## Important reality check

Qwen/Ollama is an LLM. It can create voice direction and narration guidance, but it does not synthesize real WAV audio by itself.

Recommended chain for local production:

```env
V37_VOICE_PROVIDER_CHAIN=qwen,piper,mock
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
PIPER_EXE=C:\Tools\piper\piper.exe
PIPER_VOICE=C:\Tools\piper\voices\en_US-lessac-medium.onnx
```

Safe test chain if Piper is not installed:

```env
V37_VOICE_PROVIDER_CHAIN=qwen,mock
```

## Buttons

- **Voice Providers**: checks Ollama, FFmpeg, Piper and voice status.
- **Test Voice**: quick provider test without running the production queue.
- **Generate Voice Queue**: generates missing voices using the configured chain.

## Behavior

- `qwen` creates voice-direction text under `assets/voice_prompts/`.
- `piper` creates real local WAV narration if configured.
- `mock` remains the final safety fallback for testing only.

## Expected files

```text
production/v37_voice_provider_health_latest.json
exports/v37_voice/voice_provider_health.html
exports/v37_voice/voice_provider_health.json
exports/v37_voice/voice_generation_report_latest.json
exports/v37_voice/provider_tests/provider_test_latest.json
assets/voice_prompts/*_qwen_voice_direction.txt
```
