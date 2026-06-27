# V25 Script Analysis Wizard

Adds a safer project creation workflow:

1. New Project Wizard
2. Import `.md`, `.txt`, `.docx`, `.pdf`
3. Paste full script
4. Analyze locally with Ollama/Qwen when available
5. Deterministic fallback when Ollama is unavailable
6. Preview scenes, characters, runtime and voice-only cost
7. Generate project only after review

Cost rule:
- Script analysis: local/free
- Images/music: local/free placeholders/imported assets
- Voice: only paid/API step
