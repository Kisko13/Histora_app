# Historical POV Studio v22 — Production Controller

Foundation refactor release.

New:
- `ProductionController` centralizes production task logic.
- Universal `ProductionDialog` handles voice/image/music tasks.
- Toolbar `Next Task` now opens the correct production dialog directly.
- Production Queue `Do Next Task` routes into the universal dialog.
- Scene tree shows voice/image/music badges per block.
- UI refreshes through `refresh_production_ui()` after production actions.

Run:

```bat
run_studio_v22.bat
```


## V24 Production Orchestrator

Run `run_studio_v24.bat` and open the **Control → V24 Orchestrator** tab. V24 is free-first: only voice generation can use a paid/API provider. Images and music are created as local placeholders/cue files so the project can move forward without paid image/music generation. See `docs/V24_PRODUCTION_ORCHESTRATOR.md`.
