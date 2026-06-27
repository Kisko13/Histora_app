
from __future__ import annotations
import re
from collections import Counter, defaultdict

from .models import (
    AnalysisContext, CharacterProfile, ProductionBlock,
    ProductionScene, ProductionPlan
)
from .preprocessor import split_paragraphs, word_count, first_clean_sentence


STOP_NAMES = {
    "The", "And", "But", "Then", "There", "This", "That", "Long", "Before",
    "After", "When", "Where", "What", "Why", "How", "Part", "Chapter",
    "Scene", "Production", "Script", "First", "Second", "Third",
    "Morning", "Evening", "Night", "Dawn", "Afternoon",
    "Roman", "Republic", "Battle", "War", "City", "Village",
    "Perfect", "Exactly", "Probably", "Really", "Good",
    "Everyone", "Someone", "Nobody", "Nothing", "Everything",
    "A", "An", "Of", "To", "In", "On", "For", "With"
}

LOCATION_WORDS = {
    "camp", "tent", "river", "road", "plain", "field", "battlefield", "city",
    "gate", "wall", "house", "farm", "forest", "sea", "ship", "hill", "valley",
    "village", "street", "fire", "ditch", "bridge", "mountain", "shore"
}

EQUIPMENT_WORDS = {
    "shield", "sword", "helmet", "armor", "spear", "bow", "arrow", "knife",
    "horse", "wagon", "boat", "rifle", "musket", "gun", "cloak", "boots",
    "torch", "drum", "trumpet", "standard", "banner"
}

SFX_WORDS = {
    "wind": "wind", "fire": "fire crackle", "water": "water", "river": "river",
    "horse": "horse", "horses": "horses", "scream": "scream", "screaming": "screams",
    "drum": "drums", "drums": "drums", "trumpet": "trumpet", "metal": "metal",
    "flies": "flies", "insects": "insects", "rain": "rain", "thunder": "thunder"
}


def detect_names(script: str, context: AnalysisContext) -> list[str]:
    """
    Final generic character detection.

    Priority:
    1. User-provided known characters.
    2. Main POV character.
    3. Strong repeated proper names only.
    4. Dialogue-heavy unnamed scripts -> Speaker A / Speaker B.

    This avoids treating headings, places, titles, sentence starters,
    months, and random capitalized words as characters.
    """
    explicit = set()

    for n in context.known_characters or []:
        n = (n or "").strip()
        if n:
            explicit.add(n)

    if context.main_pov_character:
        explicit.add(context.main_pov_character.strip())

    if explicit:
        return sorted(explicit)

    # Dialogue-heavy unnamed text should not invent many fake characters.
    quote_lines = [l.strip() for l in script.splitlines() if l.strip().startswith('"')]
    if len(quote_lines) >= 8:
        # If there are no clear speaker tags, use generic speakers.
        speaker_tagged = any(re.match(r"^[A-Z][A-Za-z ]{1,30}:", l) for l in script.splitlines())
        if not speaker_tagged:
            return ["Speaker A", "Speaker B"]

    bad = set(STOP_NAMES)
    bad.update(w.title() for w in LOCATION_WORDS)
    bad.update(w.title() for w in EQUIPMENT_WORDS)
    bad.update({
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December",
        "North", "South", "East", "West",
        "Rome", "Cannae", "Canusium", "Capua", "Aufidus",
        "Morning", "Perfect", "Exactly", "Probably", "Really", "Good",
        "Someone", "Everyone", "Nobody", "Nothing", "Everything",
    })

    body_lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("*") and stripped.endswith("*"):
            continue
        if len(stripped.split()) <= 6 and stripped.upper() == stripped:
            continue
        body_lines.append(stripped)

    body = "\n".join(body_lines)

    # Detect single-token names repeated strongly.
    one_word = re.findall(r"\b[A-Z][a-z]{2,}\b", body)
    one_counts = Counter(x for x in one_word if x not in bad)

    names = set()
    for name, count in one_counts.items():
        if count >= 4:
            names.add(name)

    # Detect full names, e.g. Marcus Servilius, Publius Cornelius Scipio.
    full_names = re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b", body)
    full_counts = Counter()
    for fn in full_names:
        parts = fn.split()
        if any(p in bad for p in parts):
            continue
        full_counts[fn] += 1

    for fn, count in full_counts.items():
        if count >= 1:
            # Keep first name as usable character label unless full name repeats.
            first = fn.split()[0]
            if one_counts.get(first, 0) >= 2:
                names.add(first)

    if not names:
        names.add("Narrator")

    # Cap discovered characters. Extra capitalized names become references, not production characters.
    return sorted(names)[:16]

def detect_terms(text: str, base: set[str], known: list[str]) -> list[str]:
    low = text.lower()
    out = []
    for item in known:
        if item and item.lower() in low:
            out.append(item)
    for w in base:
        if re.search(rf"\b{re.escape(w)}\b", low):
            out.append(w)
    return sorted(set(out))


def detect_sfx(text: str) -> list[str]:
    low = text.lower()
    out = []
    for key, val in SFX_WORDS.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            out.append(val)
    return sorted(set(out))


def detect_emotion(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["battle", "blood", "scream", "kill", "weapon", "impact", "push"]):
        return "battle tension"
    if any(x in low for x in ["dead", "lost", "gone", "grief", "absence"]):
        return "grief"
    if any(x in low for x in ["night", "dark", "silence", "quiet", "waiting"]):
        return "dread"
    if any(x in low for x in ["home", "mother", "father", "remember", "child"]):
        return "memory"
    return "restrained"


def estimate_duration(text: str) -> int:
    return max(6, int(word_count(text) / 2.15) + 1)


def image_prompt(text: str, context: AnalysisContext, locations: list[str], equipment: list[str], character: str, emotion: str) -> str:
    moment = re.sub(r"\s+", " ", text.strip())[:260]
    loc = ", ".join(locations) if locations else "historically accurate environment"
    eq = ", ".join(equipment) if equipment else "period-correct clothing and props"
    period = context.historical_period or "historical setting"
    return (
        f"first-person immersive historical POV still, {period}, "
        f"character focus: {character}, location: {loc}, equipment/objects: {eq}, "
        f"emotion: {emotion}, cinematic realism, natural light, human-scale composition, "
        f"no fantasy, no modern objects, narration moment: {moment}"
    )


def music_cue(emotion: str, sfx: list[str]) -> str:
    return (
        f"local/imported music only, mood: {emotion}, "
        f"sfx suggestions: {', '.join(sfx) if sfx else 'none'}, keep under narration"
    )


def split_into_scene_chunks(paragraphs: list[str]) -> list[list[str]]:
    """
    Final-ready generic scene splitter.

    Does NOT create scenes from every heading or divider.
    Targets practical production scenes around 2-4 minutes.
    Tiny fragments are merged into neighboring scenes.
    """
    scenes = []
    current = []
    current_words = 0

    def is_structural_heading(p: str) -> bool:
        low = p.lower().strip()
        wc = word_count(p)

        if wc <= 2:
            return True

        if low.startswith(("part ", "chapter ", "act ")):
            return True

        if low in {"prologue", "epilogue", "afterward", "aftermath"}:
            return True

        return False

    def is_transition(p: str) -> bool:
        low = p.lower()
        return any(x in low for x in [
            "the next morning",
            "that night",
            "years later",
            "after the battle",
            "before dawn",
            "at dusk",
            "by evening",
            "the following day",
        ])

    pending_heading = None

    for p in paragraphs:
        wc = word_count(p)

        if is_structural_heading(p):
            pending_heading = p
            continue

        hard_break = is_transition(p)
        soft_break = current_words >= 430 and wc >= 35
        max_break = current_words >= 700

        if current and (hard_break or soft_break or max_break):
            scenes.append(current)
            current = []
            current_words = 0

        if pending_heading and not current:
            # Keep heading as metadata-like first paragraph only if useful, not as its own scene.
            if word_count(pending_heading) > 2:
                current.append(pending_heading)
                current_words += word_count(pending_heading)
            pending_heading = None

        current.append(p)
        current_words += wc

    if current:
        scenes.append(current)

    # Merge very short scenes into neighbors.
    merged = []
    for sc in scenes:
        sc_words = sum(word_count(x) for x in sc)
        if merged and sc_words < 120:
            merged[-1].extend(sc)
        else:
            merged.append(sc)

    return merged

def split_blocks(scene_text: str, target_words: int = 130) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", scene_text.strip())
    blocks, cur, n = [], [], 0

    for s in sentences:
        wc = word_count(s)
        if cur and n + wc > target_words:
            blocks.append(" ".join(cur).strip())
            cur, n = [], 0
        cur.append(s)
        n += wc

    if cur:
        blocks.append(" ".join(cur).strip())

    return [b for b in blocks if b]



def production_scene_title(scene_text: str, scene_index: int) -> str:
    low = scene_text.lower()

    if "before dawn" in low or "dawn" in low:
        return "Before Dawn"
    if "tent" in low:
        return "Inside the Tent"
    if "camp" in low and "fire" in low:
        return "Campfire"
    if "river" in low or "aufidus" in low:
        return "Near the River"
    if "battle" in low or "shield" in low or "blood" in low:
        return "Battlefield"
    if "after the battle" in low or "dead" in low:
        return "Aftermath"
    if "canusium" in low or "city" in low:
        return "Refuge"

    first = first_clean_sentence(scene_text, 42)
    first = first.replace("THE FLIES ALWAYS FOUND US FIRST", "").strip()
    first = first.replace("Production Script", "").strip()
    return first or f"Scene {scene_index:03d}"


def production_block_title(text: str, block_id: str) -> str:
    t = first_clean_sentence(text, 44)
    t = t.replace("THE FLIES ALWAYS FOUND US FIRST", "").strip()
    t = t.replace("The Battle of Cannae — A First Person Narration", "").strip()
    t = t.replace("Production Script — 60–70 minutes", "").strip()
    t = t.strip(" -*#")
    return t or block_id


def character_baseline(name: str, role: str, context: AnalysisContext) -> str:
    if role == "POV narrator":
        return (
            f"{name} is the primary listener/POV character. "
            f"Voice should follow: {context.voice_style or 'restrained immersive narration'}."
        )
    return f"{name} is a supporting character detected from the script. Keep voice and visual traits consistent."


def voice_profile_for(character: str, emotion: str, context: AnalysisContext) -> dict:
    return {
        "speaker": character,
        "emotion": emotion,
        "pace": "tense controlled" if emotion == "battle tension" else "slow immersive",
        "pause_after": 0.7,
        "delivery": context.voice_style or "restrained first-person narration",
        "paid_allowed": True,
    }


def production_notes_for(block_text: str, character: str, locations: list[str], equipment: list[str]) -> dict:
    return {
        "assembly_role": "narration_block",
        "image_required": True,
        "voice_required": True,
        "music_required": True,
        "local_image_only": True,
        "local_music_only": True,
        "character_continuity": character,
        "location_continuity": locations,
        "equipment_continuity": equipment,
    }


def analyze_deterministic(script: str, context: AnalysisContext) -> dict:
    paragraphs = split_paragraphs(script)
    names = detect_names(script, context)
    scene_chunks = split_into_scene_chunks(paragraphs)

    character_scene_map = defaultdict(list)
    scenes = []
    block_number = 1

    pov = context.main_pov_character or names[0]

    for scene_index, chunk in enumerate(scene_chunks, start=1):
        scene_id = f"S{scene_index:03d}"
        scene_text = "\n\n".join(chunk)
        blocks = []

        for block_text in split_blocks(scene_text):
            block_id = f"B{block_number:04d}"
            mentioned = [n for n in names if re.search(rf"\b{re.escape(n)}\b", block_text)]

            # Never allow common words to become character labels.
            bad_character_labels = {
                "Because", "Not", "Tell", "They", "Their", "There", "This", "That",
                "Just", "Only", "Then", "When", "Where", "What", "Morning", "Evening"
            }
            mentioned = [m for m in mentioned if m not in bad_character_labels]

            if "Speaker A" in names and "Speaker B" in names and block_text.strip().startswith('"'):
                character = "Speaker A" if block_number % 2 else "Speaker B"
                mentioned = [character]
            else:
                character = mentioned[0] if mentioned else pov
            for m in mentioned or [character]:
                if scene_id not in character_scene_map[m]:
                    character_scene_map[m].append(scene_id)

            locations = detect_terms(block_text, LOCATION_WORDS, context.known_locations)
            equipment = detect_terms(block_text, EQUIPMENT_WORDS, context.known_equipment)
            sfx = detect_sfx(block_text)
            emotion = detect_emotion(block_text)
            duration = estimate_duration(block_text)

            block = ProductionBlock(
                id=block_id,
                scene_id=scene_id,
                text=block_text,
                character=character,
                duration_seconds=duration,
                voice=voice_profile_for(character, emotion, context),
                image_prompt=image_prompt(block_text, context, locations, equipment, character, emotion),
                music_cue=music_cue(emotion, sfx),
                locations=locations,
                equipment=equipment,
                sfx=sfx,
                ambience=locations or ["subtle historical room tone"],
            )

            block_dict = block.__dict__.copy()
            block_dict["title"] = production_block_title(block_text, block_id)
            block_dict["scene_label"] = block_dict["title"]
            block_dict["production_notes"] = production_notes_for(block_text, character, locations, equipment)

            blocks.append(block)
            block_number += 1

        scenes.append(ProductionScene(
            id=scene_id,
            title=production_scene_title(scene_text, scene_index),
            summary=first_clean_sentence(scene_text, 240),
            blocks=blocks,
            locations=sorted(set(x for b in blocks for x in b.locations)),
            equipment=sorted(set(x for b in blocks for x in b.equipment)),
        ))

    characters = []
    for name in names:
        scenes_for_char = character_scene_map.get(name, [])
        characters.append(CharacterProfile(
            id=name.upper().replace(" ", "_"),
            name=name,
            role="POV narrator" if name == pov else "supporting character",
            baseline=f"Detected automatically. Appears in {len(scenes_for_char)} scene(s).",
            appears_in_scenes=scenes_for_char,
        ))

    total_chars = sum(len(b.text) for s in scenes for b in s.blocks)

    plan = ProductionPlan(
        title=context.project_title,
        source="final_generic_deterministic_analyzer",
        context=context,
        characters=characters,
        scenes=scenes,
        style_bible={
            "visual_style": "cinematic historical realism, immersive first-person POV, grounded sensory detail",
            "camera": "eye-level human perspective, documentary still, no poster posing",
            "lighting": "natural practical light based on script",
            "negative_prompt": "fantasy, modern objects, modern roads, text, watermark, video game style",
        },
        production_policy={
            "paid_ai_allowed": "voice_only",
            "script_analysis": "local/free",
            "images": "local/free or placeholders",
            "music": "local/imported only",
        },
    ).to_dict()

    for s in plan["scenes"]:
        for b in s["blocks"]:
            b["title"] = production_block_title(b.get("text", ""), b.get("id", "Block"))
            b["scene_label"] = b["title"]
            b["production_notes"] = production_notes_for(
                b.get("text", ""),
                b.get("character", pov),
                b.get("locations", []),
                b.get("equipment", []),
            )

    plan["character_library"] = {
        c["id"]: {
            "name": c["name"],
            "role": c["role"],
            "baseline": c["baseline"],
            "voice_style": context.voice_style or "restrained immersive narration",
            "image_continuity": "Keep face, age, clothing, and historical equipment consistent.",
        }
        for c in plan["characters"]
    }

    plan["estimated_runtime_seconds"] = sum(b["duration_seconds"] for s in plan["scenes"] for b in s["blocks"])
    plan["estimated_voice_cost"] = total_chars * 0.000015
    return plan
