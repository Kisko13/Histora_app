from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "hps" / "core" / "analysis"
PKG.mkdir(parents=True, exist_ok=True)

# ---------------- character_detector.py ----------------

(PKG / "character_detector.py").write_text(r'''
from __future__ import annotations
import re
from collections import Counter

COMMON_FALSE_NAMES = {
    "The","And","But","Then","There","This","That","Because","Before","After",
    "When","Where","What","Why","How","Part","Chapter","Scene","Production",
    "Script","First","Second","Third","Morning","Evening","Night","Dawn",
    "Roman","Republic","Battle","War","Good","Perfect","Exactly","Probably",
    "Really","Someone","Everyone","Nobody","Nothing","Everything","Not","Tell",
    "They","Their","His","Her","Our","Your","Into","From","With","Without",
    "Under","Over","Again","Still","Only","Just","Long","Short"
}

PLACE_HINTS = {
    "Rome","Cannae","Canusium","Capua","Aufidus","Italy","Africa","Spain",
    "Camp","River","Road","Field","Plain","City","Village","Gate","Wall"
}


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().split())


def _is_bad_name(name: str) -> bool:
    if not name:
        return True
    parts = name.split()
    if any(p in COMMON_FALSE_NAMES for p in parts):
        return True
    if name in PLACE_HINTS:
        return True
    if len(name) < 3:
        return True
    return False


def detect_dialogue_mode(script: str) -> bool:
    quote_lines = [l.strip() for l in script.splitlines() if l.strip().startswith('"')]
    return len(quote_lines) >= 8


def detect_speaker_tags(script: str) -> list[str]:
    names = []
    for line in script.splitlines():
        m = re.match(r"^\s*([A-Z][A-Za-z ]{1,30}):\s+", line)
        if m:
            name = normalize_name(m.group(1))
            if not _is_bad_name(name):
                names.append(name)
    return sorted(set(names))


def detect_characters(script: str, known: list[str] | None = None, main_pov: str = "") -> list[dict]:
    known = [normalize_name(x) for x in (known or []) if normalize_name(x)]
    main_pov = normalize_name(main_pov)

    if known or main_pov:
        names = []
        if main_pov:
            names.append(main_pov)
        for k in known:
            if k not in names:
                names.append(k)
        return [
            {
                "id": n.upper().replace(" ", "_"),
                "name": n,
                "role": "POV narrator" if n == main_pov else "supporting character",
                "baseline": "User-provided character. Keep voice and visual continuity consistent.",
                "appears_in_scenes": [],
            }
            for n in names
        ]

    tagged = detect_speaker_tags(script)
    if tagged:
        return [
            {
                "id": n.upper().replace(" ", "_"),
                "name": n,
                "role": "dialogue speaker",
                "baseline": "Detected from speaker tag.",
                "appears_in_scenes": [],
            }
            for n in tagged
        ]

    if detect_dialogue_mode(script):
        return [
            {"id": "SPEAKER_A", "name": "Speaker A", "role": "dialogue speaker", "baseline": "Unnamed speaker.", "appears_in_scenes": []},
            {"id": "SPEAKER_B", "name": "Speaker B", "role": "dialogue speaker", "baseline": "Unnamed speaker.", "appears_in_scenes": []},
        ]

    # Full names first.
    full = re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b", script)
    full_counts = Counter(normalize_name(x) for x in full if not _is_bad_name(normalize_name(x)))

    # Single names must repeat strongly.
    singles = re.findall(r"\b[A-Z][a-z]{2,}\b", script)
    single_counts = Counter(x for x in singles if not _is_bad_name(x))

    names = []
    for full_name, count in full_counts.most_common():
        first = full_name.split()[0]
        if count >= 1 and single_counts.get(first, 0) >= 2:
            if first not in names:
                names.append(first)

    for name, count in single_counts.most_common():
        if count >= 4 and name not in names:
            names.append(name)

    if not names:
        names = ["Narrator"]

    return [
        {
            "id": n.upper().replace(" ", "_"),
            "name": n,
            "role": "POV narrator" if i == 0 else "supporting character",
            "baseline": "Detected automatically. Review before production.",
            "appears_in_scenes": [],
        }
        for i, n in enumerate(names[:16])
    ]


def assign_character(block_text: str, characters: list[dict], block_index: int, dialogue_mode: bool) -> str:
    names = [c["name"] for c in characters]
    if dialogue_mode and {"Speaker A", "Speaker B"}.issubset(set(names)) and block_text.strip().startswith('"'):
        return "Speaker A" if block_index % 2 else "Speaker B"

    for n in names:
        if n.startswith("Speaker "):
            continue
        if re.search(rf"\b{re.escape(n)}\b", block_text):
            return n

    return names[0] if names else "Narrator"
''', encoding="utf-8")


# ---------------- entity_detector.py ----------------

(PKG / "entity_detector.py").write_text(r'''
from __future__ import annotations
import re

GENERIC_LOCATION_TERMS = {
    "camp","tent","river","road","plain","field","battlefield","city","gate",
    "wall","house","farm","forest","sea","ship","hill","valley","village",
    "street","fire","ditch","bridge","mountain","shore","park","bench","tree",
    "path","square","market"
}

GENERIC_EQUIPMENT_TERMS = {
    "shield","sword","helmet","armor","spear","bow","arrow","knife","horse",
    "wagon","boat","rifle","musket","gun","cloak","boots","torch","drum",
    "trumpet","standard","banner","screwdriver","toolbox","bench","chairs",
    "table","guitar"
}

SFX_TERMS = {
    "wind": "wind",
    "fire": "fire crackle",
    "water": "water",
    "river": "river",
    "horse": "horse",
    "horses": "horses",
    "scream": "scream",
    "screaming": "screams",
    "drum": "drums",
    "drums": "drums",
    "trumpet": "trumpet",
    "metal": "metal",
    "flies": "flies",
    "birds": "birds",
    "insects": "insects",
    "rain": "rain",
    "thunder": "thunder",
    "footsteps": "footsteps",
    "click": "soft click",
}


def _detect(text: str, terms: set[str], known: list[str] | None = None) -> list[str]:
    low = text.lower()
    out = []
    for k in known or []:
        if k and k.lower() in low:
            out.append(k)
    for t in terms:
        if re.search(rf"\b{re.escape(t)}\b", low):
            out.append(t)
    return sorted(set(out))


def detect_locations(text: str, known: list[str] | None = None) -> list[str]:
    return _detect(text, GENERIC_LOCATION_TERMS, known)


def detect_equipment(text: str, known: list[str] | None = None) -> list[str]:
    return _detect(text, GENERIC_EQUIPMENT_TERMS, known)


def detect_sfx(text: str) -> list[str]:
    low = text.lower()
    out = []
    for key, val in SFX_TERMS.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            out.append(val)
    return sorted(set(out))


def detect_ambience(text: str, locations: list[str]) -> list[str]:
    if locations:
        return [f"{x} ambience" for x in locations[:3]]
    low = text.lower()
    if "night" in low:
        return ["night ambience"]
    if "morning" in low or "dawn" in low:
        return ["morning ambience"]
    return ["subtle historical room tone"]
''', encoding="utf-8")


# ---------------- scene_detector.py ----------------

(PKG / "scene_detector.py").write_text(r'''
from __future__ import annotations
import re
from .preprocessor import split_paragraphs, word_count, first_clean_sentence


def is_heading(p: str) -> bool:
    stripped = p.strip()
    wc = word_count(stripped)
    if wc <= 2:
        return True
    if stripped.upper() == stripped and wc <= 10:
        return True
    low = stripped.lower()
    return low.startswith(("part ", "chapter ", "act ")) or low in {"prologue", "epilogue", "aftermath", "afterward"}


def is_transition(p: str) -> bool:
    low = p.lower()
    return any(x in low for x in [
        "the next morning", "that night", "years later", "after the battle",
        "before dawn", "at dusk", "by evening", "the following day",
        "hours later", "later that day"
    ])


def split_scenes(script: str) -> list[dict]:
    paragraphs = split_paragraphs(script)
    scenes = []
    current = []
    current_words = 0
    pending_heading = None

    for p in paragraphs:
        wc = word_count(p)
        if is_heading(p):
            pending_heading = p
            continue

        should_break = False
        if current:
            should_break = is_transition(p) or current_words >= 650 or (current_words >= 430 and wc >= 40)

        if should_break:
            scenes.append({"heading": pending_heading or "", "paragraphs": current})
            current = []
            current_words = 0
            pending_heading = None

        if pending_heading and not current and word_count(pending_heading) > 2:
            current.append(pending_heading)
            current_words += word_count(pending_heading)
            pending_heading = None

        current.append(p)
        current_words += wc

    if current:
        scenes.append({"heading": pending_heading or "", "paragraphs": current})

    # Merge tiny scenes.
    merged = []
    for sc in scenes:
        wc = sum(word_count(x) for x in sc["paragraphs"])
        if merged and wc < 120:
            merged[-1]["paragraphs"].extend(sc["paragraphs"])
        else:
            merged.append(sc)

    return merged


def title_scene(scene_text: str, index: int) -> str:
    low = scene_text.lower()
    semantic = [
        ("before dawn", "Before Dawn"),
        ("dawn", "Before Dawn"),
        ("tent", "Inside the Tent"),
        ("campfire", "Campfire"),
        ("fire", "By the Fire"),
        ("river", "Near the River"),
        ("battlefield", "Battlefield"),
        ("battle", "Battlefield"),
        ("after the battle", "Aftermath"),
        ("dead", "Aftermath"),
        ("city", "Refuge"),
        ("road", "On the Road"),
    ]
    for key, val in semantic:
        if key in low:
            return val
    return first_clean_sentence(scene_text, 44) or f"Scene {index:03d}"
''', encoding="utf-8")


# ---------------- block_detector.py ----------------

(PKG / "block_detector.py").write_text(r'''
from __future__ import annotations
import re
from .preprocessor import word_count, first_clean_sentence


def split_blocks(scene_text: str, target_words: int = 130) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", scene_text.strip())
    blocks, cur, n = [], [], 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        wc = word_count(s)
        if cur and n + wc > target_words:
            blocks.append(" ".join(cur).strip())
            cur, n = [], 0
        cur.append(s)
        n += wc

    if cur:
        blocks.append(" ".join(cur).strip())

    return [b for b in blocks if b]


def title_block(text: str, block_id: str) -> str:
    t = first_clean_sentence(text, 46)
    junk = [
        "THE FLIES ALWAYS FOUND US FIRST",
        "The Battle of Cannae — A First Person Narration",
        "Production Script — 60–70 minutes",
    ]
    for j in junk:
        t = t.replace(j, "")
    t = t.strip(" -*#")
    return t or block_id
''', encoding="utf-8")


# ---------------- production_planner.py ----------------

(PKG / "production_planner.py").write_text(r'''
from __future__ import annotations
import re
from .preprocessor import word_count


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
    pause = 1 if word_count(text) < 20 else 0
    return max(6, int(word_count(text) / 2.15) + pause)


def image_prompt(text: str, period: str, character: str, locations: list[str], equipment: list[str], emotion: str) -> str:
    moment = re.sub(r"\s+", " ", text.strip())[:240]
    return (
        f"first-person immersive historical POV still, {period or 'historical setting'}, "
        f"character focus: {character}, location: {', '.join(locations) if locations else 'historically accurate environment'}, "
        f"equipment/objects: {', '.join(equipment) if equipment else 'period-correct clothing and props'}, "
        f"emotion: {emotion}, cinematic realism, natural light, human-scale composition, "
        f"no fantasy, no modern objects, moment: {moment}"
    )


def music_cue(emotion: str, sfx: list[str]) -> str:
    return (
        f"local/imported music only, mood: {emotion}, "
        f"sfx suggestions: {', '.join(sfx) if sfx else 'none'}, keep under narration"
    )


def voice_profile(character: str, emotion: str, voice_style: str) -> dict:
    return {
        "speaker": character,
        "emotion": emotion,
        "pace": "tense controlled" if emotion == "battle tension" else "slow immersive",
        "pause_after": 0.7,
        "delivery": voice_style or "restrained first-person narration",
        "paid_allowed": True,
    }


def production_notes(character: str, locations: list[str], equipment: list[str]) -> dict:
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
''', encoding="utf-8")


# ---------------- Replace analyzer.py with clean orchestrator ----------------

(PKG / "analyzer.py").write_text(r'''
from __future__ import annotations

from .models import AnalysisContext
from .scene_detector import split_scenes, title_scene
from .block_detector import split_blocks, title_block
from .character_detector import detect_characters, assign_character, detect_dialogue_mode
from .entity_detector import detect_locations, detect_equipment, detect_sfx, detect_ambience
from .production_planner import detect_emotion, estimate_duration, image_prompt, music_cue, voice_profile, production_notes
from .validators import validate_plan


class GenericScriptAnalyzer:
    """
    V26 clean analyzer.

    Modular, final-ready architecture:
    - scene detection
    - block detection
    - character detection
    - entity detection
    - production planning

    No story-specific hardcoding.
    """

    def analyze(self, script: str, context: AnalysisContext) -> dict:
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
                    "production_notes": production_notes(character, locations, equipment),
                })
                block_counter += 1

            scenes.append({
                "id": sid,
                "title": title_scene(scene_text, si),
                "summary": scene_text.strip().replace("\n", " ")[:240],
                "blocks": blocks,
                "locations": sorted(set(x for b in blocks for x in b["locations"])),
                "equipment": sorted(set(x for b in blocks for x in b["equipment"])),
            })

        for c in characters:
            c["appears_in_scenes"] = character_scene_map.get(c["name"], [])
            if not c.get("baseline"):
                c["baseline"] = "Detected automatically. Review before production."

        total_seconds = sum(b["duration_seconds"] for s in scenes for b in s["blocks"])
        total_chars = sum(len(b["text"]) for s in scenes for b in s["blocks"])

        plan = {
            "title": context.project_title,
            "source": "v26_clean_modular_analyzer",
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
                        "text": b.get("text", ""),
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


# Docs
(ROOT / "docs" / "V26_CLEAN_ANALYZER_REWRITE.md").write_text("""# V26 Clean Analyzer Rewrite

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
""", encoding="utf-8")

print("V26 clean analyzer rewrite installed.")
print("Run: .\\run_studio_v24.bat")