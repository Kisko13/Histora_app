from pathlib import Path

ROOT = Path(__file__).resolve().parent
analyzer = ROOT / "hps" / "core" / "analysis" / "analyzer.py"

txt = analyzer.read_text(encoding="utf-8")

marker = '''    def analyze(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        dialogue_mode = detect_dialogue_mode(script)
        tagged_mode = has_speaker_tags(script)

        raw_scenes = split_scenes(script)
        scenes = []
        block_counter = 1
'''

replacement = '''    def analyze(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        dialogue_mode = detect_dialogue_mode(script)
        tagged_mode = has_speaker_tags(script)

        scenes = []
        block_counter = 1

        # Tagged scripts are authoritative:
        # [Marcus] is metadata, text below it is clean voice text.
        if tagged_mode:
            tagged_blocks = parse_tagged_script(script, context.main_pov_character or "Narrator")

            # Drop empty/system junk.
            tagged_blocks = [
                tb for tb in tagged_blocks
                if tb.text.strip()
                and tb.text.strip().upper() not in {"ENDOFSCRIPT", "ECHO \\"DONE\\""}
            ]

            scene_groups = []
            current = []

            for tb in tagged_blocks:
                t = tb.text.strip()
                is_heading = (
                    tb.speaker.lower() == "narrator"
                    and (
                        t.startswith("#")
                        or t.startswith("*")
                        or "PART " in t.upper()
                        or "EPILOGUE" in t.upper()
                    )
                )

                if current and is_heading:
                    scene_groups.append(current)
                    current = []

                if not is_heading:
                    current.append(tb)

                if len(current) >= 6:
                    scene_groups.append(current)
                    current = []

            if current:
                scene_groups.append(current)

            character_scene_map = {c["name"]: [] for c in characters}

            for si, group in enumerate(scene_groups, 1):
                sid = f"S{si:03d}"
                blocks = []

                scene_text = "\\n\\n".join(tb.text for tb in group)

                for tb in group:
                    bid = f"B{block_counter:04d}"
                    block_text = tb.text.strip()
                    character = tb.speaker.strip() or "Narrator"

                    if character in character_scene_map and sid not in character_scene_map[character]:
                        character_scene_map[character].append(sid)

                    locations = detect_locations(block_text, context.known_locations)
                    equipment = detect_equipment(block_text, context.known_equipment)
                    sfx = detect_sfx(block_text)
                    ambience = detect_ambience(block_text, locations)
                    emotion = detect_emotion(block_text)
                    duration = estimate_duration(block_text)

                    blocks.append({
                        "id": bid,
                        "scene_id": sid,
                        "title": title_block(block_text, bid),
                        "scene_label": title_block(block_text, bid),
                        "text": block_text,
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
                            "speaker_tag_source": True,
                            "speaker_tag_directives": tb.directives,
                            "voice_text_clean": True,
                        },
                    })
                    block_counter += 1

                scenes.append({
                    "id": sid,
                    "title": title_scene(scene_text, si),
                    "summary": scene_text.strip().replace("\\n", " ")[:240],
                    "blocks": blocks,
                    "locations": sorted(set(x for b in blocks for x in b["locations"])),
                    "equipment": sorted(set(x for b in blocks for x in b["equipment"])),
                })

            for c in characters:
                c["appears_in_scenes"] = character_scene_map.get(c["name"], [])

            total_seconds = sum(b["duration_seconds"] for s in scenes for b in s["blocks"])
            total_chars = sum(len(b["text"]) for s in scenes for b in s["blocks"])

            plan = {
                "title": context.project_title,
                "source": "v26_tagged_script_analyzer",
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

        raw_scenes = split_scenes(script)
'''

if marker not in txt:
    raise RuntimeError("Could not find analyzer header block.")

txt = txt.replace(marker, replacement)
analyzer.write_text(txt, encoding="utf-8")

print("Tagged mode fix applied.")