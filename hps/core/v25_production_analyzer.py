
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Any


WORD_RE = re.compile(r"\S+")


@dataclass
class Character:
    id: str
    name: str
    voice_type: str = "narrator"
    gender: str = "unknown"
    estimated_age: str = "unknown"
    appears_in_scenes: list[str] = field(default_factory=list)


@dataclass
class NarrationBlock:
    id: str
    scene_id: str
    character: str
    text: str
    estimated_seconds: int
    emotion: str
    pace: str
    pause_after: float
    image_prompt: str
    music_mood: str
    sfx: list[str]
    ambience: list[str]


@dataclass
class ImageCue:
    id: str
    scene_id: str
    block_id: str
    prompt: str
    camera: str
    lighting: str
    mood: str


@dataclass
class MusicCue:
    id: str
    scene_id: str
    block_id: str
    mood: str
    intensity: int
    note: str


@dataclass
class Scene:
    id: str
    title: str
    summary: str
    location: str
    estimated_seconds: int
    blocks: list[NarrationBlock] = field(default_factory=list)
    image_cues: list[ImageCue] = field(default_factory=list)
    music_cues: list[MusicCue] = field(default_factory=list)


@dataclass
class ProductionPlan:
    title: str
    source: str
    created_at: float
    estimated_runtime_seconds: int
    estimated_voice_cost: float
    characters: list[Character]
    scenes: list[Scene]
    production_policy: dict[str, Any]
    style_bible: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CHARACTER_NAMES = [
    "Marcus", "Titus", "Gaius", "Publius", "Quintus", "Decimus", "Vibius",
    "Lucius", "Flavius", "Varro", "Paullus", "Hannibal", "Scipio", "Fabius",
    "Gnaeus", "Cassius"
]

LOCATIONS = {
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

SFX = {
    "flies": "flies buzzing",
    "fly": "flies buzzing",
    "horse": "horse",
    "horses": "horses",
    "trumpet": "trumpet",
    "bucina": "bucina",
    "drum": "drums",
    "drums": "drums",
    "shield": "shield impact",
    "shields": "shield impacts",
    "metal": "metal impacts",
    "fire": "campfire",
    "wind": "wind",
    "dust": "dust wind",
    "screaming": "screams",
    "scream": "scream",
    "insects": "insects",
    "water": "water",
    "river": "river",
}

AMBIENCE = {
    "dawn": "pre-dawn camp",
    "night": "night camp",
    "camp": "Roman camp ambience",
    "tent": "tent interior",
    "river": "riverbank ambience",
    "battle": "battlefield chaos",
    "battlefield": "battlefield chaos",
    "plain": "open dusty plain",
    "road": "marching road",
    "fire": "campfire ambience",
    "city": "city refuge",
    "canusium": "Canusium refuge",
}


def words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def wc(text: str) -> int:
    return len(words(text))


def clean_title(text: str, max_len: int = 56) -> str:
    text = re.sub(r"[*#_\-]+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0]
    return text or "Untitled Scene"


def split_paragraphs(script: str) -> list[str]:
    script = script.replace("\r\n", "\n")
    parts = re.split(r"\n\s*\n+", script)
    return [p.strip() for p in parts if p.strip()]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def detect_location(text: str) -> str:
    low = text.lower()
    found = []
    for k, v in LOCATIONS.items():
        if k in low:
            found.append(v)
    return found[0] if found else "historical environment"


def detect_tags(text: str, mapping: dict[str, str]) -> list[str]:
    low = text.lower()
    out = []
    for k, v in mapping.items():
        if k in low and v not in out:
            out.append(v)
    return out


def detect_characters(text: str) -> list[str]:
    out = []
    for name in CHARACTER_NAMES:
        if re.search(rf"\b{name}\b", text):
            out.append("MARCUS" if name == "Marcus" else name)
    return out or ["MARCUS"]


def detect_emotion(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["battle", "shield", "gladius", "blood", "scream", "impact", "push"]):
        return "battle tension"
    if any(x in low for x in ["dead", "gone", "grief", "absence", "lost"]):
        return "grief"
    if any(x in low for x in ["silence", "quiet", "dark", "waiting"]):
        return "dread"
    if any(x in low for x in ["mother", "home", "farm", "remember"]):
        return "memory"
    if any(x in low for x in ["heat", "dust", "thirst", "tired", "sleep"]):
        return "exhaustion"
    return "restrained"


def detect_pace(text: str) -> str:
    low = text.lower()
    if wc(text) < 18:
        return "very slow"
    if any(x in low for x in ["run", "impact", "push", "scream", "battle"]):
        return "tense controlled"
    return "slow immersive"


def detect_pause(text: str) -> float:
    low = text.lower()
    pause = 0.45
    if "silence" in low:
        pause = 2.0
    if wc(text) < 12:
        pause = max(pause, 1.1)
    if "..." in text:
        pause = max(pause, 1.3)
    if text.strip().endswith("—"):
        pause = max(pause, 1.0)
    return round(pause, 2)


def estimate_seconds(text: str, pause: float) -> int:
    # slow narration around 125–135 WPM
    return max(6, int(wc(text) / 2.15 + pause + 0.2 * max(0, len(split_sentences(text)) - 1)))


def image_prompt(text: str, location: str, chars: list[str], emotion: str) -> str:
    moment = re.sub(r"\s+", " ", text.strip())[:260]
    return (
        "first-person immersive historical POV still, cinematic realism, "
        f"location: {location}, characters/tags: {', '.join(chars)}, emotion: {emotion}, "
        "period-correct Roman Republic equipment, natural light, dusty atmosphere, "
        "human scale, no fantasy, no modern objects, "
        f"scene moment: {moment}"
    )


def music_mood(emotion: str) -> str:
    if emotion == "battle tension":
        return "low aggressive battle tension"
    if emotion == "grief":
        return "subtle mournful drone"
    if emotion == "dread":
        return "quiet ominous tension"
    if emotion == "memory":
        return "soft distant memory texture"
    if emotion == "exhaustion":
        return "dry minimal fatigue ambience"
    return "restrained historical ambience"


def should_new_scene(paragraph: str, current_words: int, previous_location: str) -> bool:
    low = paragraph.lower()
    if paragraph.startswith("#") or paragraph.startswith("##"):
        return True
    if current_words > 650:
        return True
    if any(x in low for x in ["part one", "part two", "part three", "part four", "part five"]):
        return True
    loc = detect_location(paragraph)
    if previous_location != "historical environment" and loc != previous_location and wc(paragraph) > 80:
        return True
    if any(x in low for x in ["---", "the morning", "that night", "after the battle", "we advance", "we run"]):
        return True
    return False


def make_blocks(scene_id: str, text: str, start_index: int) -> tuple[list[NarrationBlock], list[ImageCue], list[MusicCue], int]:
    sentences = split_sentences(text)
    chunks = []
    cur = []
    cur_words = 0

    for s in sentences:
        sw = wc(s)
        if cur and cur_words + sw > 135:
            chunks.append(" ".join(cur))
            cur = []
            cur_words = 0
        cur.append(s)
        cur_words += sw

    if cur:
        chunks.append(" ".join(cur))

    blocks = []
    images = []
    music = []
    idx = start_index

    for chunk in chunks:
        chars = detect_characters(chunk)
        loc = detect_location(chunk)
        emotion = detect_emotion(chunk)
        pace = detect_pace(chunk)
        pause = detect_pause(chunk)
        seconds = estimate_seconds(chunk, pause)
        bid = f"B{idx:04d}"

        prompt = image_prompt(chunk, loc, chars, emotion)
        mood = music_mood(emotion)
        sfx = detect_tags(chunk, SFX)
        ambience = detect_tags(chunk, AMBIENCE) or ["subtle historical room tone"]

        block = NarrationBlock(
            id=bid,
            scene_id=scene_id,
            character=chars[0],
            text=chunk,
            estimated_seconds=seconds,
            emotion=emotion,
            pace=pace,
            pause_after=pause,
            image_prompt=prompt,
            music_mood=mood,
            sfx=sfx,
            ambience=ambience,
        )
        blocks.append(block)

        # One image per block for now. Later we can generate more for longer blocks.
        images.append(ImageCue(
            id=f"IMG_{bid}",
            scene_id=scene_id,
            block_id=bid,
            prompt=prompt,
            camera="eye-level first-person POV, 35mm documentary still",
            lighting="natural practical light based on scene",
            mood=emotion,
        ))

        if idx == start_index or emotion in ["battle tension", "grief", "dread", "memory"]:
            intensity = 4 if emotion == "battle tension" else 2
            music.append(MusicCue(
                id=f"MUS_{bid}",
                scene_id=scene_id,
                block_id=bid,
                mood=mood,
                intensity=intensity,
                note="Local/imported music only. Keep under narration."
            ))

        idx += 1

    return blocks, images, music, idx


def build_production_plan(script: str, title: str = "Historical POV Project") -> dict[str, Any]:
    paragraphs = split_paragraphs(script)
    scenes_raw = []
    current = []
    current_words = 0
    previous_location = "historical environment"

    for p in paragraphs:
        if current and should_new_scene(p, current_words, previous_location):
            scenes_raw.append("\n\n".join(current))
            current = []
            current_words = 0
        current.append(p)
        current_words += wc(p)
        previous_location = detect_location(p)

    if current:
        scenes_raw.append("\n\n".join(current))

    scenes = []
    block_index = 1
    character_scene_map: dict[str, set[str]] = {}

    for i, scene_text in enumerate(scenes_raw, 1):
        sid = f"S{i:03d}"
        location = detect_location(scene_text)
        blocks, images, music, block_index = make_blocks(sid, scene_text, block_index)
        seconds = sum(b.estimated_seconds for b in blocks)

        for b in blocks:
            for ch in detect_characters(b.text):
                character_scene_map.setdefault(ch, set()).add(sid)

        scenes.append(Scene(
            id=sid,
            title=clean_title(scene_text),
            summary=re.sub(r"\s+", " ", scene_text.strip())[:280],
            location=location,
            estimated_seconds=seconds,
            blocks=blocks,
            image_cues=images,
            music_cues=music,
        ))

    characters = []
    for name, scene_ids in sorted(character_scene_map.items()):
        characters.append(Character(
            id=name,
            name=name,
            voice_type="POV narrator" if name == "MARCUS" else "supporting character",
            gender="male" if name not in [] else "unknown",
            estimated_age="adult",
            appears_in_scenes=sorted(scene_ids),
        ))

    if not characters:
        characters.append(Character(
            id="MARCUS",
            name="MARCUS",
            voice_type="POV narrator",
            gender="male",
            estimated_age="adult",
            appears_in_scenes=[s.id for s in scenes],
        ))

    total_seconds = sum(s.estimated_seconds for s in scenes)
    total_chars = sum(len(b.text) for s in scenes for b in s.blocks)

    plan = ProductionPlan(
        title=title,
        source="v25_local_production_analyzer",
        created_at=time.time(),
        estimated_runtime_seconds=total_seconds,
        estimated_voice_cost=total_chars * 0.000015,
        characters=characters,
        scenes=scenes,
        production_policy={
            "paid_ai_allowed": "voice_only",
            "script_analysis": "local/free deterministic parser, Ollama optional later",
            "images": "local generation or placeholders only",
            "music": "imported/local only",
            "cloud_llm": "not required",
        },
        style_bible={
            "visual_style": "cinematic historical realism, first-person sensory memory",
            "camera": "eye-level first-person POV, 35mm documentary still",
            "lighting": "natural practical light, dust, smoke, dawn, firelight, sunset when appropriate",
            "negative_prompt": "fantasy armor, horns, spikes, modern objects, modern roads, text, watermark, video game style",
        },
    )
    return plan.to_dict()


def plan_metrics(plan: dict[str, Any]) -> dict[str, Any]:
    scenes = plan.get("scenes", [])

    blocks = []
    images = []
    music = []

    for s in scenes:
        blocks.extend(s.get("blocks", []))
        images.extend(s.get("image_cues", []))
        music.extend(s.get("music_cues", []))

    words = 0
    for b in blocks:
        words += len((b.get("text") or "").split())

    runtime = plan.get("estimated_runtime_seconds", 0) / 60

    voice_cost = (
        plan.get("estimated_voice_cost")
        or plan.get("voice_cost")
        or 0.0
    )

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(plan.get("characters", [])),
        "locations": 0,
        "equipment": 0,
        "words": words,
        "runtime_minutes": runtime,
        "voice_cost": voice_cost,
        "images": len(images),
        "music_cues": len(music),
    }


def plan_to_legacy_importer_shape(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Converts V25 plan to the existing ScriptImporter apply_plan shape.
    """
    out = {
        "title": plan.get("title", "Historical POV Project"),
        "source": plan.get("source", "v25"),
        "characters": plan.get("characters", []),
        "scenes": [],
        "production_policy": plan.get("production_policy", {}),
        "style_bible": plan.get("style_bible", {}),
    }

    for s in plan.get("scenes", []):
        blocks = []
        for b in s.get("blocks", []):
            blocks.append({
                "id": b.get("id"),
                "text": b.get("text", ""),
                "scene_label": b.get("id", ""),
                "duration_seconds": b.get("estimated_seconds", 10),
                "characters": [b.get("character", "MARCUS")],
                "locations": [s.get("location", "")],
                "voice": {
                    "emotion": b.get("emotion", "restrained"),
                    "pace": b.get("pace", "slow immersive"),
                    "pause_after": b.get("pause_after", 0.45),
                    "delivery": "first-person memory, restrained, sensory",
                },
                "image_prompt": b.get("image_prompt", ""),
                "music_cue": b.get("music_mood", ""),
                "sfx": b.get("sfx", []),
                "ambience": b.get("ambience", []),
            })

        out["scenes"].append({
            "id": s.get("id"),
            "title": s.get("title"),
            "summary": s.get("summary", ""),
            "blocks": blocks,
        })

    return out
