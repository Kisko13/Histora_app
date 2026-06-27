
from __future__ import annotations


def validate_plan(plan: dict) -> tuple[bool, list[str]]:
    errors = []

    if not isinstance(plan, dict):
        return False, ["Plan is not a dictionary."]

    if not plan.get("title"):
        errors.append("Missing title.")

    if not plan.get("scenes"):
        errors.append("No scenes detected.")

    for s in plan.get("scenes", []):
        if not s.get("id"):
            errors.append("Scene missing id.")
        if not s.get("blocks"):
            errors.append(f"Scene {s.get('id', '?')} has no blocks.")
        for b in s.get("blocks", []):
            if not b.get("text"):
                errors.append(f"Block {b.get('id', '?')} has no text.")
            if not b.get("image_prompt"):
                errors.append(f"Block {b.get('id', '?')} missing image prompt.")
            if not b.get("music_cue"):
                errors.append(f"Block {b.get('id', '?')} missing music cue.")

    return len(errors) == 0, errors
