# v9.1 Qwen Engine Fixes

Changed:

1. Qwen TTS endpoint corrected to:

```text
/services/aigc/multimodal-generation/generation
```

2. TTS payload corrected:
- `input.text`
- `input.voice`
- `input.instructions` when using instruct model
- `parameters.sample_rate`
- `parameters.response_format`

3. Audio extraction now checks:
- `output.audio.url`
- `output.audio.data`
- `output.audios[0].url`
- nested audio URL / base64 fallbacks

4. Config check is local/free only.
It does not send a paid request.

5. Sidecar/error responses are no longer treated as clean generated audio.
They are marked `needs_inspection`.

6. Fresh setup batch file added:

```bat
run_studio_v91.bat
```

7. `.env.example` now includes:
- `QWEN_WORKSPACE_ID`
- conservative `MAX_BUILD_COST_USD=0.50`
- pricing estimate `0.0115` per 1k chars

## Next test order

1. Run app.
2. Select B001.
3. One-Block Qwen Test.
4. Check Config (Free).
5. Dry-run ON.
6. Generate One Block.
7. If dry-run sidecar looks right:
   - edit `.env`
   - set `ALLOW_PAID_GENERATION=true`
   - uncheck dry-run
   - generate one tiny sentence first.
