
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
