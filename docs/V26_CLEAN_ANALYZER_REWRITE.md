# V26 Clean Analyzer Rewrite

Production-ready modular rewrite.

New modules:

- character_detector.py
- entity_detector.py
- scene_detector.py
- block_detector.py
- production_planner.py
- analyzer.py

Purpose:

Replace fragile regex patch stack with a maintainable architecture.

Pipeline:

Script
→ Scene detector
→ Block detector
→ Character detector
→ Entity detector
→ Production planner
→ Validated ProductionPlan
→ Project generator

No Cannae-specific hardcoding.
No paid AI in analysis.
Voice remains the only paid step.
