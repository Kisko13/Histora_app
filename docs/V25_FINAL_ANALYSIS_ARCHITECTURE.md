# V25 Final Analysis Architecture

Final-ready generic analysis system.

Modules:

- hps/core/analysis/models.py
- hps/core/analysis/preprocessor.py
- hps/core/analysis/deterministic.py
- hps/core/analysis/validators.py
- hps/core/analysis/analyzer.py

Rules:

- No script-specific hardcoding.
- No Cannae-specific character list.
- No paid AI in analysis.
- Voice remains the only paid/API step.
- Analyzer receives optional context from the wizard.
- Empty context still works by discovery.

The old prototype analyzers remain in the repo temporarily but the wizard now uses:

GenericScriptAnalyzer
