# V24 Big Local AI Step

This build adds the large missing production step: the app can now take a full script and split it into production-ready scenes/blocks without paid AI.

## Cost policy

Only voice generation is allowed to spend money.

Everything below is local/free:

- Script splitting
- Scene planning
- Image prompts
- Style Bible injection
- Character/location/equipment asset library
- Music cues
- Director report
- Recovery snapshots
- Image/music placeholder generation
- Assembly outputs

## New workflow

Open project, then go to:

`V24 Orchestrator -> Paste Full Script → Local AI Split`

Paste the complete script and press `Split Script + Replace Project`.

The app will try local Ollama/Qwen first:

- Host: `http://127.0.0.1:11434`
- Model default: `qwen2.5:7b`

If Ollama is not running or Qwen returns bad JSON, the app automatically falls back to deterministic free splitting. This means the workflow still works even without local AI installed.

## Output created

The splitter creates:

- Scenes
- Blocks
- Narration text per block
- Voice direction metadata
- Image prompts per block
- Music cues per block
- Style Bible
- Asset library
- Production plan JSON

Files are saved under:

- `production/script_plan_latest.json`
- `production/style_bible.json`
- `assets/library/asset_index.json`
- `assets/library/characters/`
- `assets/library/locations/`
- `assets/library/equipment/`

## Next step after splitting

Press:

`Rebuild Plan`

Then:

`Run V24 Pipeline`

Leave `Also run voice generation` OFF unless you intentionally want to use the paid voice provider. With voice OFF, the pipeline prepares everything local/free and marks voice jobs as waiting.

## Ollama setup reminder

Install Ollama, then run one of these in CMD:

```bat
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

For your RTX 3060 8 GB, start with 7B. Use 14B only if performance is acceptable.
