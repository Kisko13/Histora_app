
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
