from pathlib import Path
from hps.storage.db import ProjectDB

project_path = Path("projects/cannae_001/cannae_001.hps")
db = ProjectDB(project_path).connect()
project_id = "cannae_001"
db.upsert_project(project_id, "The Flies Always Found Us First", "You Wake Up Before the Battle of Cannae (216 BC)", "60-70")

for s in [
    ("S001", "Before Dawn — The Flies", "Opening hook.", "camp_before_dawn", "none", "flies_river_leather", 1),
    ("S002", "The Tent", "Character introductions.", "tent_interior", "low_warm_ambient", "quiet_camp_tent", 2),
    ("S003", "Example Dialogue", "Titus example line.", "camp_fire", "none", "quiet_fire", 3),
]:
    db.execute("INSERT OR REPLACE INTO scenes(id, project_id, title, summary, visual_theme, music_profile, sfx_profile, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (s[0], project_id, s[1], s[2], s[3], s[4], s[5], s[6]))

voice_states = {
    "M1_CALM_MEMORY": "Quiet, intimate, controlled. Slow pace. Long natural pauses. Never theatrical.",
    "M2_WARM_MEMORY": "Warmer and conversational. Subtle human humor. Restrained nostalgia.",
    "M4_COMBAT_COMPRESSION": "Controlled survival mode. Tighter breath. Clipped delivery. Not shouting.",
    "T1_DRY_VETERAN": "Dry, low, factual. Every word weighed. No drama."
}
for vid, prompt in voice_states.items():
    db.execute("INSERT OR REPLACE INTO voice_states(id, project_id, delivery_prompt) VALUES (?, ?, ?)", (vid, project_id, prompt))

for v in [
    ("MARCUS_001", "Marcus Main Narrator", "mock", "", "", "not_created", "Main narrator"),
    ("TITUS_001", "Titus Veteran", "mock", "", "", "not_created", "Dry veteran"),
]:
    db.execute("INSERT OR REPLACE INTO voices(id, project_id, display_name, provider, provider_voice_id, source_audio_path, clone_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (v[0], project_id, v[1], v[2], v[3], v[4], v[5], v[6]))

for c in [
    ("MARCUS", "narrator_protagonist", "MARCUS_001", "intimate, restrained, memory-heavy", ""),
    ("TITUS", "veteran_soldier", "TITUS_001", "dry, tired, factual", ""),
]:
    db.execute("INSERT OR REPLACE INTO characters(id, project_id, role, actor_voice_id, baseline, notes) VALUES (?, ?, ?, ?, ?, ?)", (c[0], project_id, c[1], c[2], c[3], c[4]))

blocks = [
    ("B001", "S001", "MARCUS", "M1_CALM_MEMORY", "Opening - The Flies",
     "The flies always found us before dawn.\n\nLong before Hannibal.\n\nLong before the screaming.\n\nLong before Rome lost more sons than anyone believed possible in a single afternoon on a flat and unremarkable plain in the south of Italy.\n\nThe flies always found us first.",
     "Wide cinematic Roman camp before dawn, flies over leather straps, low river mist, historically grounded, 16:9.", "Roman camp dawn — almost silent, low drone", 1),
    ("B002", "S002", "MARCUS", "M2_WARM_MEMORY", "Character Introductions",
     "The tent I shared had seven other men in it.\n\nThere was Gaius. There was Titus. There was young Publius from Arretium.\n\nPaste or import the full production script here as blocks.",
     "Interior of Roman soldiers tent before dawn, dim oil lamp, tired faces, intimate, grounded, 16:9.", "Warm low tent ambience", 1),
    ("B003", "S003", "TITUS", "T1_DRY_VETERAN", "Titus Example Line",
     "\"Wet.\"",
     "Older Roman veteran close-up near camp fire, dry expression, worn helmet, 16:9.", "No music, only fire", 1),
]
for b in blocks:
    db.execute("""
        INSERT OR REPLACE INTO blocks(id, project_id, scene_id, character_id, voice_state_id, scene_label, text, status, image_prompt, music_cue, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'missing', ?, ?, ?)
    """, (b[0], project_id, b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8]))
print(f"Created sample project: {project_path}")
