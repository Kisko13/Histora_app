
from __future__ import annotations

from .models import AnalysisContext
from .deterministic import analyze_deterministic
from .validators import validate_plan


class GenericScriptAnalyzer:
    """
    Final-ready generic analyzer facade.

    It is intentionally script-agnostic:
    no Roman/Cannae/Viking/WW1 hardcoding.
    Specific context is passed through AnalysisContext.
    """

    def analyze(self, script: str, context: AnalysisContext) -> dict:
        plan = analyze_deterministic(script, context)
        ok, errors = validate_plan(plan)
        plan["validation"] = {"ok": ok, "errors": errors}
        return plan


def plan_metrics(plan: dict) -> dict:
    scenes = plan.get("scenes", [])
    blocks = [b for s in scenes for b in s.get("blocks", [])]
    locations = set(x for b in blocks for x in b.get("locations", []))
    equipment = set(x for b in blocks for x in b.get("equipment", []))
    sfx = set(x for b in blocks for x in b.get("sfx", []))

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(plan.get("characters", [])),
        "locations": len(locations),
        "equipment": len(equipment),
        "sfx": len(sfx),
        "ambience": len(set(x for b in blocks for x in b.get("ambience", []))),
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
                        "scene_label": b.get("id", ""),
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
