# V26 Voice Clean Text Safety

Adds permanent voice safety helpers:

- removes `[Speaker]` tags before TTS
- refuses paid voice generation if tags remain
- saves a `voice_request.json` audit file beside generated audio

This protects the only paid step in the pipeline.
