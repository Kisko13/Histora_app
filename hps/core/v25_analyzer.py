
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from typing import Any

WORD_RE = re.compile(r"\S+")

KNOWN_LOCATIONS = {
    "camp": "Roman camp",
    "tent": "Roman tent",
    "river": "Aufidus river",
    "aufidus": "Aufidus river",
    "plain": "Cannae plain",
    "cannae": "Cannae battlefield",
    "battlefield": "Cannae battlefield",
    "road": "road",
    "rome": "Rome",
    "capua": "Capua",
    "canusium": "Canusium",
    "field": "field",
    "ditch": "ditch",
    "gate": "city gate",
    "wall": "city wall",
    "fire": "campfire",
}

KNOWN_EQUIPMENT = {
    "scutum": "scutum",
    "shield": "scutum",
    "gladius": "gladius",
    "pilum": "pilum",
    "pila": "pila",
    "helmet": "Roman helmet",
    "chin strap": "helmet chin strap",
    "caligae": "caligae",
    "hobnails": "hobnailed sandals",
    "armor": "Roman armor",
    "mail": "mail armor",
    "sword": "sword",
    "spear": "spear",
    "standard": "Roman standard",
    "bucina": "bucina",
    "trumpet": "trumpet",
}

SFX_RULES = {
    "horse": "horse movement / horse scream",
    "horses": "horse movement / horse scream",
    "trumpet": "distant trumpet",
    "bucina": "Roman bucina",
    "drum": "enemy drums",
    "drums": "enemy drums",
    "fire": "campfire crackle",
    "flies": "flies buzzing",
    "fly": "flies buzzing",
    "wind": "dry wind",
    "dust": "wind through dust",
    "screaming": "distant screams",
    "scream": "distant screams",
    "metal": "metal impacts",
    "shield": "shield impact",
    "shields": "shield wall impacts",
    "feet": "marching feet",
    "hobnails": "hobnails on hard earth",
    "water": "river water",
    "river": "river ambience",
    "insects": "evening insects",
    "bird": "distant bird",
}

AMBIENCE_RULES = {
    "camp": "low Roman camp ambience",
    "tent": "muffled tent interior",
    "river": "riverbank ambience",
    "aufidus": "riverbank ambience",
    "plain": "open dusty plain",
    "battle": "dense battlefield chaos",
    "battlefield": "dense battlefield chaos",
    "night": "night camp ambience",
    "dawn": "pre-dawn camp",
    "fire": "campfire ambience",
    "road": "march road ambience",
    "city": "city survivor refuge",
    "canusium": "Canusium refuge ambience",
}

EMOTION_RULES = [
    ("panic", ["panic", "cannot breathe", "suffocat", "trapped", "crush", "compression"]),
    ("battle shock", ["blood", "scream", "dead", "kill", "impact", "gladius", "stab"]),
    ("dread", ["dark", "waiting", "silence", "quiet", "something changes", "not finished"]),
    ("memory", ["remember", "mother", "home", "farm", "Capua"]),
    ("exhaustion", ["tired", "thirst", "heat", "dust", "sleep", "body"]),
    ("grief", ["dead", "gone", "absence", "not see them again", "grief"]),
]

CHARACTER_CANDIDATES = [
    "Marcus", "Titus", "Gaius", "Publius", "Quintus", "Decimus", "Vibius",
    "Lucius", "Flavius", "Varro", "Paullus", "Hannibal", "Scipio", "Fabius"
]


def words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def word_count(text: str) -> int:
    return len(words(text))


def split_sentences(text: str) -> list[str]:
    text = (text or "").replace("\r\n", "\n")
    parts = re.split(r"(?<=[.!?])\s+|\n\s*\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def detect_character_mentions(text: str) -> list[str]:
    found = []
    for name in CHARACTER_CANDIDATES:
        if re.search(rf"\b{re.escape(name)}\b", text):
            found.append(name.upper() if name == "Marcus" else name)
    return found or ["MARCUS"]


def detect_tags(text: str, rules: dict[str, str]) -> list[str]:
    low = text.lower()
    out = []
    for key, value in rules.items():
        if key in low and value not in out:
            out.append(value)
    return out


def detect_locations(text: str) -> list[str]:
    return detect_tags(text, KNOWN_LOCATIONS)


def detect_equipment(text: str) -> list[str]:
    return detect_tags(text, KNOWN_EQUIPMENT)


def detect_sfx(text: str) -> list[str]:
    return detect_tags(text, SFX_RULES)


def detect_ambience(text: str) -> list[str]:
    found = detect_tags(text, AMBIENCE_RULES)
    return found or ["subtle historical room tone"]


def detect_emotion(text: str) -> str:
    low = text.lower()
    scores = Counter()
    for emotion, keys in EMOTION_RULES:
        for key in keys:
            if key in low:
                scores[emotion] += 1
    if scores:
        return scores.most_common(1)[0][0]
    if word_count(text) < 20:
        return "quiet emphasis"
    return "restrained immersive narration"


def detect_pace(text: str) -> str:
    wc = word_count(text)
    low = text.lower()
    if wc < 20 or "silence" in low:
        return "very slow"
    if any(x in low for x in ["run", "impact", "scream", "push", "battle", "panic"]):
        return "tense controlled"
    return "slow"


def detect_pause(text: str) -> float:
    low = text.lower()
    pause = 0.45
    if "silence" in low:
        pause = max(pause, 2.0)
    if re.search(r"\.\s*\.\s*\.", text):
        pause = max(pause, 1.2)
    if text.strip().endswith("—"):
        pause = max(pause, 0.9)
    if word_count(text) < 12:
        pause = max(pause, 1.0)
    return round(pause, 2)


def estimate_duration(text: str, pause_after: float = 0.5) -> int:
    # Slow narration: about 125–135 WPM plus pauses.
    wc = word_count(text)
    base = wc / 2.15
    sentence_pause = max(0, len(split_sentences(text)) - 1) * 0.22
    return max(5, int(base + sentence_pause + pause_after))


def image_prompt_for_block(text: str, locations: list[str], equipment: list[str], characters: list[str]) -> str:
    loc = ", ".join(locations[:3]) if locations else "historically accurate environment"
    eq = ", ".join(equipment[:5]) if equipment else "period-correct clothing and equipment"
    chars = ", ".join(characters[:4]) if characters else "POV narrator"
    moment = re.sub(r"\s+", " ", text.strip())[:260]
    return (
        "first-person immersive historical POV still, cinematic realism, "
        f"characters/tags: {chars}, location: {loc}, equipment: {eq}, "
        "natural light, grounded human details, no fantasy elements, "
        f"narration moment: {moment}"
    )


def music_cue_for_block(text: str, emotion: str, ambience: list[str], sfx: list[str]) -> str:
    intensity = 2
    if emotion in {"panic", "battle shock"}:
        intensity = 5
    elif emotion in {"dread", "grief"}:
        intensity = 3

    return (
        f"LOCAL/IMPORTED music only; mood={emotion}; intensity={intensity}/5; "
        f"ambience={', '.join(ambience[:4])}; "
        f"sfx={', '.join(sfx[:5]) if sfx else 'none'}; "
        "keep under narration, no paid music generation"
    )


def make_characters(script: str) -> list[dict[str, str]]:
    counts = Counter()
    for name in CHARACTER_CANDIDATES:
        counts[name] = len(re.findall(rf"\b{re.escape(name)}\b", script))

    chars = [{
        "id": "MARCUS",
        "role": "POV narrator / listener character",
        "baseline": "Roman infantryman, farmer's son from outside Capua, physically tired, emotionally restrained, historically plausible equipment."
    }]

    role_map = {
        "Titus": "older veteran in the contubernium",
        "Gaius": "large soldier in Marcus's tent group",
        "Publius": "young underage recruit",
        "Quintus": "tent-mate / Roman soldier",
        "Decimus": "tent-mate / Roman soldier",
        "Vibius": "Samnite allied soldier",
        "Lucius": "Roman soldier / battlefield presence",
        "Flavius": "centurion or officer figure",
        "Varro": "Roman consul",
        "Paullus": "Roman consul",
        "Hannibal": "Carthaginian commander, historical figure",
        "Scipio": "Roman officer, historical figure",
        "Fabius": "Roman statesman/general, historical figure",
    }

    for name, count in counts.most_common():
        if name == "Marcus" or count <= 0:
            continue
        chars.append({
            "id": name.upper() if name == "Marcus" else name,
            "role": role_map.get(name, "mentioned character"),
            "baseline": f"Detected in script {count} time(s). Keep visually and narratively consistent."
        })

    return chars


def chunk_blocks(script: str, target_words: int = 135) -> list[str]:
    units = split_sentences(script)
    if not units:
        return []

    blocks = []
    cur = []
    count = 0

    for unit in units:
        wc = word_count(unit)
        force_short = wc < 15 and any(x in unit.lower() for x in ["silence", "dawn", "rome", "dead", "alive"])
        if cur and (count + wc > target_words or force_short):
            blocks.append(" ".join(cur).strip())
            cur, count = [], 0
        cur.append(unit)
        count += wc
    if cur:
        blocks.append(" ".join(cur).strip())

    return [b for b in blocks if b]


def scene_title_from_block(text: str, scene_no: int) -> str:
    clean = re.sub(r"[*#_\-]+", "", text).strip()
    clean = re.sub(r"\s+", " ", clean)
    if len(clean) > 54:
        clean = clean[:54].rsplit(" ", 1)[0]
    return clean or f"Scene {scene_no:03d}"


def build_v25_plan(script: str, title: str = "Historical POV Project", target_words: int = 135) -> dict[str, Any]:
    blocks = chunk_blocks(script, target_words=target_words)
    characters = make_characters(script)

    scenes = []
    block_no = 1
    blocks_per_scene = 5

    for scene_no in range(1, math.ceil(len(blocks) / blocks_per_scene) + 1):
        scene_blocks = blocks[(scene_no - 1) * blocks_per_scene: scene_no * blocks_per_scene]
        scene_items = []
        scene_locations = set()
        scene_equipment = set()
        scene_sfx = set()
        scene_ambience = set()

        for text in scene_blocks:
            chars = detect_character_mentions(text)
            locs = detect_locations(text)
            eq = detect_equipment(text)
            sfx = detect_sfx(text)
            ambience = detect_ambience(text)
            emotion = detect_emotion(text)
            pace = detect_pace(text)
            pause_after = detect_pause(text)
            duration = estimate_duration(text, pause_after)

            scene_locations.update(locs)
            scene_equipment.update(eq)
            scene_sfx.update(sfx)
            scene_ambience.update(ambience)

            scene_items.append({
                "id": f"block_{block_no:03d}",
                "text": text,
                "scene_label": f"Segment {block_no:03d}",
                "voice": {
                    "emotion": emotion,
                    "pace": pace,
                    "pause_after": pause_after,
                    "delivery": "first-person memory, restrained, sensory, no announcer tone"
                },
                "image_prompt": image_prompt_for_block(text, locs, eq, chars),
                "music_cue": music_cue_for_block(text, emotion, ambience, sfx),
                "duration_seconds": duration,
                "characters": chars,
                "locations": locs,
                "equipment": eq,
                "sfx": sfx,
                "ambience": ambience,
                "production_notes": {
                    "paid_allowed": "voice_only",
                    "image_generation": "local_or_placeholder",
                    "music_generation": "local_import_only",
                    "assembly_hint": "block duration follows estimated voice duration"
                }
            })
            block_no += 1

        first = scene_blocks[0] if scene_blocks else ""
        scenes.append({
            "id": f"scene_{scene_no:03d}",
            "title": scene_title_from_block(first, scene_no),
            "summary": re.sub(r"\s+", " ", first.strip())[:260],
            "visual_theme": "cinematic historical realism, first-person sensory memory, historically grounded props and clothing",
            "music_profile": f"local/imported ambience bed; {', '.join(sorted(scene_ambience)[:4])}",
            "sfx_profile": ", ".join(sorted(scene_sfx)) if scene_sfx else "none",
            "locations": sorted(scene_locations),
            "equipment": sorted(scene_equipment),
            "blocks": scene_items,
        })

    return {
        "title": title or "Historical POV Project",
        "source": "v25_local_deterministic_analyzer",
        "style_bible": {
            "visual_style": "cinematic historical realism, immersive first-person POV, grounded sensory details, no fantasy",
            "camera": "35mm documentary still, eye-level human POV, natural perspective, no heroic poster posing",
            "lighting": "natural practical light, dust haze, smoke, dawn/firelight/sunset when script supports it",
            "negative_prompt": "fantasy armor, horns, spikes, modern objects, modern roads, text, watermark, exaggerated muscles, video-game style"
        },
        "characters": characters,
        "scenes": scenes,
        "production_policy": {
            "paid_ai_allowed": "voice_only",
            "script_analysis": "local_or_deterministic_free",
            "images": "local_generation_or_placeholders",
            "music": "imported_or_local_only",
            "cloud_llm": "not_required"
        }
    }


def enrich_plan(plan: dict[str, Any], original_script: str = "") -> dict[str, Any]:
    """
    Takes either Qwen/Ollama JSON or deterministic JSON and fills missing V25 fields.
    """
    if not isinstance(plan, dict):
        return build_v25_plan(original_script)

    if not plan.get("characters"):
        plan["characters"] = make_characters(original_script or json.dumps(plan))

    for si, scene in enumerate(plan.get("scenes", []) or [], 1):
        scene.setdefault("id", f"scene_{si:03d}")
        scene.setdefault("title", f"Scene {si:03d}")
        scene.setdefault("summary", "")
        scene.setdefault("visual_theme", "cinematic historical realism, first-person sensory POV")
        scene.setdefault("music_profile", "local/imported ambience bed")
        scene.setdefault("sfx_profile", "optional local SFX only")

        for bi, block in enumerate(scene.get("blocks", []) or [], 1):
            text = block.get("text", "")
            chars = block.get("characters") or detect_character_mentions(text)
            locs = block.get("locations") or detect_locations(text)
            eq = block.get("equipment") or detect_equipment(text)
            sfx = block.get("sfx") or detect_sfx(text)
            ambience = block.get("ambience") or detect_ambience(text)
            emotion = (block.get("voice") or {}).get("emotion") or detect_emotion(text)
            pace = (block.get("voice") or {}).get("pace") or detect_pace(text)
            pause_after = (block.get("voice") or {}).get("pause_after")
            if pause_after is None:
                pause_after = detect_pause(text)

            block.setdefault("id", f"block_{si:03d}_{bi:02d}")
            block.setdefault("scene_label", f"Segment {si:03d}-{bi:02d}")
            block["characters"] = chars
            block["locations"] = locs
            block["equipment"] = eq
            block["sfx"] = sfx
            block["ambience"] = ambience
            block["voice"] = {
                **(block.get("voice") or {}),
                "emotion": emotion,
                "pace": pace,
                "pause_after": pause_after,
                "delivery": (block.get("voice") or {}).get("delivery", "first-person memory, restrained, sensory")
            }
            block["duration_seconds"] = int(block.get("duration_seconds") or estimate_duration(text, float(pause_after)))
            block["image_prompt"] = block.get("image_prompt") or image_prompt_for_block(text, locs, eq, chars)
            block["music_cue"] = block.get("music_cue") or music_cue_for_block(text, emotion, ambience, sfx)
            block["production_notes"] = {
                **(block.get("production_notes") or {}),
                "paid_allowed": "voice_only",
                "image_generation": "local_or_placeholder",
                "music_generation": "local_import_only",
            }

    plan.setdefault("style_bible", build_v25_plan(original_script).get("style_bible"))
    plan.setdefault("production_policy", {
        "paid_ai_allowed": "voice_only",
        "script_analysis": "local_or_deterministic_free",
        "images": "local_generation_or_placeholders",
        "music": "imported_or_local_only",
    })
    return plan


def plan_metrics(plan: dict[str, Any]) -> dict[str, Any]:
    scenes = plan.get("scenes") or []
    blocks = [b for s in scenes for b in (s.get("blocks") or [])]
    chars = plan.get("characters") or []

    locs = set()
    eq = set()
    sfx = set()
    ambience = set()
    duration = 0
    chars_total = 0
    words_total = 0

    for b in blocks:
        text = b.get("text", "")
        words_total += word_count(text)
        chars_total += len(text)
        duration += int(b.get("duration_seconds") or estimate_duration(text))
        locs.update(b.get("locations") or [])
        eq.update(b.get("equipment") or [])
        sfx.update(b.get("sfx") or [])
        ambience.update(b.get("ambience") or [])

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(chars),
        "locations": len(locs),
        "equipment": len(eq),
        "sfx": len(sfx),
        "ambience": len(ambience),
        "words": words_total,
        "characters_total": chars_total,
        "runtime_seconds": duration,
        "runtime_minutes": duration / 60 if duration else 0,
        "voice_cost_estimate": chars_total * 0.000015,
        "image_music_analysis_cost": 0.0,
    }
