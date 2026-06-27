# V25 Generic Analyzer Fixes

Adds final-ready improvements:

1. Character confidence scoring
- ignores headings/common words
- repeated names only
- user-provided known characters override detection
- unnamed dialogue fallback becomes Speaker A / Speaker B

2. Better scene rules
- headings are metadata, not automatic scenes
- short fragments are merged
- target production scenes around 2-4 minutes

3. Analyzer context fields in wizard
- Main POV character
- Known characters
- Known locations
- Known equipment

No story-specific Cannae hardcoding added.
