# V25 Production Analyzer

This upgrade turns the script wizard into a stronger production planner.

It adds:

- deterministic local analysis even when Ollama is unavailable
- character mention detection
- location detection
- equipment detection
- SFX cue detection
- ambience cue detection
- pause detection from script rhythm
- block duration estimation
- voice emotion/pace metadata
- first-person image prompt creation
- local/import-only music cues
- voice-only cost estimation

Cost policy remains unchanged:

- Script analysis: free/local
- Images: local or placeholder
- Music: imported/local only
- Voice: the only paid/API step

The full plan is saved as:

`production/script_plan_latest.json`
