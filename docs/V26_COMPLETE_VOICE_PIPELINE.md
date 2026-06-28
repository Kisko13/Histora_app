# V26 Complete Voice Pipeline

Adds end-to-end clean voice generation safety.

When Generate Voice runs:

1. Reads selected block text.
2. Removes speaker tags like `[Marcus]`.
3. Refuses generation if tags remain.
4. Generates mock `.wav` for provider `mock`.
5. Saves an audit file beside the audio:

`B0001_marcus_voice_request.json`

The JSON contains the exact clean text sent to voice generation.

Real paid providers should be connected through `hps/core/voice_pipeline.py` so all paid voice generation passes through the same safety checks.
