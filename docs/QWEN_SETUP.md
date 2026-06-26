# Qwen Voice API Setup

This project prepares Qwen usage behind safety controls.

## What is implemented

- Qwen config check
- Qwen Voice Design dry-run
- Qwen Voice Design real-call scaffold
- Qwen TTS dry-run
- Qwen TTS real-call scaffold
- cost warnings
- paid calls disabled unless enabled in `.env`

## Important official notes

Alibaba Cloud Model Studio's Qwen-TTS docs show non-real-time speech synthesis through `dashscope.MultiModalConversation.call` with model `qwen3-tts-flash`, an API key, text, and voice parameter. The docs also note workspace-specific domains for Beijing and Singapore regions. Voice Design creates a custom voice from a text description, returns preview audio, and for Qwen-TTS voice design is billed per voice creation after free quota/eligibility.

## Required `.env`

```env
DASHSCOPE_API_KEY=your_key
QWEN_WORKSPACE_ID=your_workspace_id
QWEN_REGION=singapore
ALLOW_PAID_GENERATION=false
```

Keep this false while testing the UI:

```env
ALLOW_PAID_GENERATION=false
```

Only set it true when you intentionally want real paid calls:

```env
ALLOW_PAID_GENERATION=true
```

## Safe testing order

1. Open app.
2. Go to `Qwen Voice Lab`.
3. Keep `Dry run / no paid request` checked.
4. Click `Check API Config`.
5. Click `Create/Test Voice Design`.
6. Click `Create Test TTS`.

Only after the dry-run payload looks correct should you disable dry-run and enable paid generation in `.env`.

## Reality check

The Qwen API response shape may differ by region, workspace, and model version. The first real TTS call saves a response sidecar if direct audio extraction needs adjustment. That is intentional so we can inspect your real response once and then finalize the audio-saving code.
