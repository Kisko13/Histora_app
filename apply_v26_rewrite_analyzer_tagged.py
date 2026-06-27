from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "hps" / "core" / "analysis"
analyzer = PKG / "analyzer.py"

analyzer.write_text(r'''
from __future__ import annotations

from .models import AnalysisContext
from .scene_detector import split_scenes, title_scene
from .block_detector import split_blocks, title_block
from .character_detector import detect_characters, assign_character, detect_dialogue_mode
from .entity_detector import detect_locations, detect_equipment, detect_sfx, detect_ambience
from .production_planner import detect_emotion, estimate_duration, image_prompt, music_cue, voice_profile, production_notes
from .validators import validate_plan
from .speaker_tags import has_speaker_tags, parse_tagged_script


class GenericScriptAnalyzer:
    """
    V26 clean analyzer with authoritative [Speaker] tag support.

    If script has tags like:

    [Marcus]
    Text here.

    then:
    - speaker = Marcus
    - voice text = Text here
    - tag is never sent to voice generation
    """

    def analyze(self, script: str, context: AnalysisContext) -> dict:
        if has_speaker_tags(script):
            return self._analyze_tagged(script, context)
        return self._analyze_untagged(script, context)

    def _base_plan(self, context: AnalysisContext, characters: list[dict], scenes: list[dict], source: str) -> dict:
        total_seconds = sum(b["duration_seconds"] for s in scenes for b in s["blocks"])
        total_chars = sum(len(b["text"]) for s in scenes for b in s["blocks"])

        plan = {
            "title": context.project_title,
            "source": source,
            "context": context.__dict__,
            "characters": characters,
            "character_library": {
                c["id"]: {
                    "name": c["name"],
                    "role": c["role"],
                    "baseline": c["baseline"],
                    "voice_style": context.voice_style or "restrained immersive narration",
                    "image_continuity": "Keep face, age, clothing, and historical equipment consistent.",
                }
                for c in characters
            },
            "scenes": scenes,
            "estimated_runtime_seconds": total_seconds,
            "estimated_voice_cost": total_chars * 0.000015,
            "style_bible": {
                "visual_style": "cinematic historical realism, immersive first-person POV, grounded sensory detail",
                "camera": "eye-level human perspective, documentary still, no poster posing",
                "lighting": "natural practical light based on script",
                "negative_prompt": "fantasy, modern objects, modern roads, text, watermark, video game style",
            },
            "production_policy": {
                "paid_ai_allowed": "voice_only",
                "script_analysis": "local/free",
                "images": "local/free or placeholders",
                "music": "local/imported only",
            },
        }

        ok, errors = validate_plan(plan)
        plan["validation"] = {"ok": ok, "errors": errors}
        return plan

    def _make_block(self, bid: str, sid: str, block_text: str, character: str, context: AnalysisContext, tagged: bool, directives=None) -> dict:
        directives = directives or []
        locations = detect_locations(block_text, context.known_locations)
        equipment = detect_equipment(block_text, context.known_equipment)
        sfx = detect_sfx(block_text)
        ambience = detect_ambience(block_text, locations)
        emotion = detect_emotion(block_text)
        duration = estimate_duration(block_text)

        return {
            "id": bid,
            "scene_id": sid,
            "title": title_block(block_text, bid),
            "scene_label": title_block(block_text, bid),
            "text": block_text.strip(),
            "character": character,
            "duration_seconds": duration,
            "voice": voice_profile(character, emotion, context.voice_style),
            "image_prompt": image_prompt(block_text, context.historical_period, character, locations, equipment, emotion),
            "music_cue": music_cue(emotion, sfx),
            "locations": locations,
            "equipment": equipment,
            "sfx": sfx,
            "ambience": ambience,
            "production_notes": {
                **production_notes(character, locations, equipment),
                "speaker_tag_source": tagged,
                "speaker_tag_directives": directives,
                "voice_text_clean": True,
            },
        }

    def _analyze_tagged(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        tagged_blocks = parse_tagged_script(script, context.main_pov_character or "Narrator")

        # Remove shell/file junk if it accidentally exists at bottom.
        tagged_blocks = [
            tb for tb in tagged_blocks
            if tb.text.strip()
            and tb.text.strip().upper() not in {"ENDOFSCRIPT", 'ECHO "DONE"'}
        ]

        scene_groups = []
        current = []

        for tb in tagged_blocks:
            text = tb.text.strip()
            speaker = tb.speaker.strip()

            structural = (
                speaker.lower() == "narrator"
                and (
                    text.startswith("#")
                    or text.startswith("---")
                    or text.startswith("*END")
                    or "PART " in text.upper()
                    or "EPILOGUE" in text.upper()
                )
            )

            if current and structural:
                scene_groups.append(current)
                current = []

            if not structural:
                current.append(tb)

            # production scene size, not every tag
            if len(current) >= 6:
                scene_groups.append(current)
                current = []

        if current:
            scene_groups.append(current)

        scenes = []
        block_counter = 1
        character_scene_map = {c["name"]: [] for c in characters}

        for si, group in enumerate(scene_groups, 1):
            sid = f"S{si:03d}"
            blocks = []
            scene_text = "\n\n".join(tb.text.strip() for tb in group)

            for tb in group:
                bid = f"B{block_counter:04d}"
                clean_text = tb.text.strip()
                character = tb.speaker.strip() or "Narrator"

                if character in character_scene_map and sid not in character_scene_map[character]:
                    character_scene_map[character].append(sid)

                blocks.append(self._make_block(
                    bid=bid,
                    sid=sid,
                    block_text=clean_text,
                    character=character,
                    context=context,
                    tagged=True,
                    directives=tb.directives,
                ))
                block_counter += 1

            scenes.append({
                "id": sid,
                "title": title_scene(scene_text, si),
                "summary": scene_text.replace("\n", " ")[:240],
                "blocks": blocks,
                "locations": sorted(set(x for b in blocks for x in b["locations"])),
                "equipment": sorted(set(x for b in blocks for x in b["equipment"])),
            })

        for c in characters:
            c["appears_in_scenes"] = character_scene_map.get(c["name"], [])

        return self._base_plan(context, characters, scenes, "v26_tagged_script_analyzer")

    def _analyze_untagged(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        dialogue_mode = detect_dialogue_mode(script)
        raw_scenes = split_scenes(script)

        scenes = []
        block_counter = 1
        character_scene_map = {c["name"]: [] for c in characters}

        for si, raw in enumerate(raw_scenes, 1):
            sid = f"S{si:03d}"
            scene_text = "\n\n".join(raw["paragraphs"])
            blocks = []

            for block_text in split_blocks(scene_text):
                bid = f"B{block_counter:04d}"
                character = assign_character(block_text, characters, block_counter, dialogue_mode)

                if character in character_scene_map and sid not in character_scene_map[character]:
                    character_scene_map[character].append(sid)

                blocks.append(self._make_block(
                    bid=bid,
                    sid=sid,
                    block_text=block_text,
                    character=character,
                    context=context,
                    tagged=False,
                    directives=[],
                ))
                block_counter += 1

            scenes.append({
                "id": sid,
                "title": title_scene(scene_text, si),
                "summary": scene_text.replace("\n", " ")[:240],
                "blocks": blocks,
                "locations": sorted(set(x for b in blocks for x in b["locations"])),
                "equipment": sorted(set(x for b in blocks for x in b["equipment"])),
            })

        for c in characters:
            c["appears_in_scenes"] = character_scene_map.get(c["name"], [])

        return self._base_plan(context, characters, scenes, "v26_clean_modular_analyzer")


def plan_metrics(plan: dict) -> dict:
    scenes = plan.get("scenes", [])
    blocks = [b for s in scenes for b in s.get("blocks", [])]
    locations = set(x for b in blocks for x in b.get("locations", []))
    equipment = set(x for b in blocks for x in b.get("equipment", []))
    sfx = set(x for b in blocks for x in b.get("sfx", []))
    ambience = set(x for b in blocks for x in b.get("ambience", []))

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(plan.get("characters", [])),
        "locations": len(locations),
        "equipment": len(equipment),
        "sfx": len(sfx),
        "ambience": len(ambience),
        "images": len(blocks),
        "music_cues": len(blocks),
        "words": sum(len((b.get("text") or "").split()) for b in blocks),
        "runtime_minutes": (plan.get("estimated_runtime_seconds", 0) or 0) / 60,
        "voice_cost": plan.get("estimated_voice_cost", 0.0) or 0.0,
    }


def plan_to_legacy_importer_shape(plan: dict) -> dict:
    return {
        "title": plan.get("title", "Historical POV Project"),
        "source": plan.get("source", "generic_analysis"),
        "characters": plan.get("characters", []),
        "scenes": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "summary": s.get("summary", ""),
                "blocks": [
                    {
                        "id": b.get("id"),
                        "text": b.get("text", ""),  # clean voice text; no [Speaker] tag
                        "scene_label": b.get("scene_label") or b.get("title") or b.get("id", ""),
                        "duration_seconds": b.get("duration_seconds", 10),
                        "characters": [b.get("character", "Narrator")],
                        "locations": b.get("locations", []),
                        "equipment": b.get("equipment", []),
                        "voice": b.get("voice", {}),
                        "image_prompt": b.get("image_prompt", ""),
                        "music_cue": b.get("music_cue", ""),
                        "sfx": b.get("sfx", []),
                        "ambience": b.get("ambience", []),
                        "production_notes": b.get("production_notes", {}),
                    }
                    for b in s.get("blocks", [])
                ],
            }
            for s in plan.get("scenes", [])
        ],
        "style_bible": plan.get("style_bible", {}),
        "production_policy": plan.get("production_policy", {}),
    }
''', encoding="utf-8")

print("Analyzer rewritten with robust tagged-script support.")
print("Run: .\\run_studio_v24.bat")