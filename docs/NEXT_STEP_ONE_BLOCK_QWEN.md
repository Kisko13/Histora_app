# Next Step: One-Block Qwen Test

The next milestone is not a whole episode. It is one sentence or one selected block.

## Safe test

1. Run `run_studio_v9.bat`.
2. Select B001 in the left scene tree.
3. Open `One-Block Qwen Test`.
4. Click `Load Current Block`.
5. Keep `Dry run / no paid request` checked.
6. Click `Estimate Cost`.
7. Click `Generate One Block`.

This should create a `.dryrun.json` payload and add it as an audio version with zero cost.

## Real test

Only after dry-run looks good:

1. Put your Qwen details in `.env`.
2. Set:

```env
ALLOW_PAID_GENERATION=true
```

3. Uncheck dry-run.
4. Click `Generate One Block`.

The app will:
- warn you about estimated cost
- send one Qwen request
- save the audio if the response contains an audio URL/base64 data
- otherwise save the full response sidecar for inspection

## Why sidecar matters

Qwen/DashScope response shapes can differ by model, region, and account. The first real response tells us exactly where the WAV/audio URL is in your account response, then the extractor can be finalized.
