# v10 Voice Generation Dialog

The core workflow is now:

```text
Select Block → Generate Voice → Review Settings → Generate → Version saved
```

## Dry-run test

1. Select `B001`.
2. Click `Generate Voice`.
3. Provider: `qwen`.
4. Keep `Dry run / no paid Qwen request` checked.
5. Click `Generate`.

This creates a dry-run JSON payload and saves it as a version with zero cost.

## First real paid test

Fill `.env`:

```env
DASHSCOPE_API_KEY=...
QWEN_WORKSPACE_ID=...
QWEN_REGION=singapore
ALLOW_PAID_GENERATION=true
MAX_BUILD_COST_USD=0.50
```

Then:

1. Select `B001`.
2. Click `Generate Voice`.
3. Provider: `qwen`.
4. Use a tiny text first.
5. Uncheck dry-run.
6. Generate.

If audio extraction succeeds, the WAV is saved. If not, a `.response.json` sidecar is saved and the status becomes `needs_inspection`.
