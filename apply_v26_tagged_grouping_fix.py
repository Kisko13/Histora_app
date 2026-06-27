from pathlib import Path

ROOT = Path(__file__).resolve().parent
analyzer = ROOT / "hps" / "core" / "analysis" / "analyzer.py"

txt = analyzer.read_text(encoding="utf-8")

# Fix character detection in tagged mode by deriving from tagged blocks directly
txt = txt.replace(
'''        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        tagged_blocks = parse_tagged_script(script, context.main_pov_character or "Narrator")''',
'''        tagged_blocks = parse_tagged_script(script, context.main_pov_character or "Narrator")

        speaker_names = []
        for tb in tagged_blocks:
            n = tb.speaker.strip()
            if n and n not in speaker_names:
                speaker_names.append(n)

        characters = [
            {
                "id": n.upper().replace(" ", "_"),
                "name": n,
                "role": "POV narrator" if n.lower() in {"marcus", "narrator"} else "script speaker",
                "baseline": "Detected from [Speaker] production tag. Tag is metadata and is not sent to voice generation.",
                "appears_in_scenes": [],
            }
            for n in speaker_names
            if n.lower() not in {"endofscript", "echo"}
        ]'''
)

# Replace scene grouping + block loop in tagged analyzer with proper merged production blocks
start = txt.find("        scene_groups = []", txt.find("    def _analyze_tagged"))
end = txt.find("        for c in characters:", start)

if start == -1 or end == -1:
    raise RuntimeError("Could not find tagged grouping section.")

replacement = r'''        # First group tagged paragraphs into production-sized blocks.
        # Tags remain metadata; voice text stays clean.
        production_blocks = []
        current_speaker = None
        current_directives = []
        current_texts = []
        current_words = 0

        def flush_block():
            nonlocal current_speaker, current_directives, current_texts, current_words
            text = "\n\n".join(t.strip() for t in current_texts if t.strip()).strip()
            if text:
                production_blocks.append({
                    "speaker": current_speaker or "Narrator",
                    "directives": list(current_directives),
                    "text": text,
                })
            current_speaker = None
            current_directives = []
            current_texts = []
            current_words = 0

        def count_words(t):
            return len((t or "").split())

        for tb in tagged_blocks:
            text = tb.text.strip()
            speaker = tb.speaker.strip() or "Narrator"

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

            if structural:
                flush_block()
                continue

            w = count_words(text)

            # Start a new block when speaker changes or block gets too large.
            if current_texts and (speaker != current_speaker or current_words + w > 130):
                flush_block()

            current_speaker = speaker
            current_directives = tb.directives
            current_texts.append(text)
            current_words += w

        flush_block()

        # Now group production blocks into scenes.
        scene_groups = []
        current_scene = []
        current_scene_words = 0

        for pb in production_blocks:
            w = count_words(pb["text"])
            if current_scene and (current_scene_words + w > 650 or len(current_scene) >= 6):
                scene_groups.append(current_scene)
                current_scene = []
                current_scene_words = 0

            current_scene.append(pb)
            current_scene_words += w

        if current_scene:
            scene_groups.append(current_scene)

        scenes = []
        block_counter = 1
        character_scene_map = {c["name"]: [] for c in characters}

        for si, group in enumerate(scene_groups, 1):
            sid = f"S{si:03d}"
            blocks = []
            scene_text = "\n\n".join(pb["text"] for pb in group)

            for pb in group:
                bid = f"B{block_counter:04d}"
                clean_text = pb["text"].strip()
                character = pb["speaker"].strip() or "Narrator"

                if character in character_scene_map and sid not in character_scene_map[character]:
                    character_scene_map[character].append(sid)

                blocks.append(self._make_block(
                    bid=bid,
                    sid=sid,
                    block_text=clean_text,
                    character=character,
                    context=context,
                    tagged=True,
                    directives=pb["directives"],
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

'''
txt = txt[:start] + replacement + txt[end:]

analyzer.write_text(txt, encoding="utf-8")

print("V26 tagged grouping fix applied.")
print("Run: .\\run_studio_v24.bat")