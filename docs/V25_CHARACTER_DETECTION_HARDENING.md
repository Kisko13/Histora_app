# V25 Character Detection Hardening

Improves generic character detection:

- If known characters are provided, use them as the authoritative list.
- If main POV character is provided, include it.
- Dialogue-only unnamed scripts become Speaker A / Speaker B.
- Capitalized words must repeat strongly to become characters.
- Locations, headings, weekdays, months, directions, and common sentence starters are ignored.
- Discovered character list is capped to avoid noisy projects.

No Cannae-specific logic was added to the analyzer flow.
