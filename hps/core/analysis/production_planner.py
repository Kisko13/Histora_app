
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
