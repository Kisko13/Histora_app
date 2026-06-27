
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
