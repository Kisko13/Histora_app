# V28 Visual Slots + Scene Music

This version changes the production model to match listening-first YouTube episodes.

## New production rules

- Voice remains block-based.
- Images are **visual slots**, not one image per block.
- Music is **scene-based**, not one music cue per block.

Recommended workflow for a 60-75 min episode:

- 10-20 visual slots total, usually 15.
- 1 music bed/cue per scene.
- Voice generated per block.

## New files

- `hps/core/visual_slot_plan.py`
- `hps/core/scene_music_plan.py`

## New/updated UI

Toolbar now includes:

- `Plan Visual/Music`
- `Generate Missing Assets`

## Outputs

Visual plan:

`projects/<project>/production/visual_slot_plan.json`

Visual slot mock assets:

`projects/<project>/assets/visual_slots/VIS001/approved.txt`

Block visual pointers:

`projects/<project>/assets/images/B0001/approved.txt`

Scene music plan:

`projects/<project>/production/scene_music_plan.json`

Scene music mock assets:

`projects/<project>/assets/scene_music/S001/approved.txt`

Block music pointers:

`projects/<project>/assets/music/B0001/approved.txt`

## Testing

1. Open app.
2. Click `Plan Visual/Music`.
3. Enter `15` or `3` for small test.
4. Check `production/visual_slot_plan.json` and `production/scene_music_plan.json`.
5. Click `Generate Missing Assets`.
6. Enter `3` for voice test.
7. Enter `3` for visual slot test.
8. Confirm report shows voices, visual slots, scene music.

