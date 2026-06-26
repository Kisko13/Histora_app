"""V24 local AI-style production director. Rule-based, offline, no paid API calls."""
from __future__ import annotations

import json
from pathlib import Path
from hps.core.block_state import compute_project_state


class ProductionDirector:
    def __init__(self, db):
        self.db = db

    def analyze_block(self, block_id: str) -> dict:
        from hps.core.block_state import compute_block_state
        b = self.db.block_with_scene(block_id)
        state = compute_block_state(self.db, block_id)
        text = (b["text"] or "").strip()
        warnings = []
        recommendations = []
        if len(text) < 120:
            warnings.append("Script block is very short; narration may feel abrupt.")
        if len(text) > 1800:
            warnings.append("Script block is long; consider splitting for better pacing and image matching.")
        if not (b["image_prompt"] or "").strip():
            recommendations.append("Create an image prompt before real image generation or manual image search.")
        if not (b["music_cue"] or "").strip():
            recommendations.append("Create a music/SFX cue so assembly has direction without paid generation.")
        if not state["voice_ok"]:
            recommendations.append("Generate/approve voice first because it controls final timing.")
        elif not state["image_ok"]:
            recommendations.append("Approve image or placeholder next.")
        elif not state["music_ok"]:
            recommendations.append("Approve local music/SFX cue or silent placeholder next.")
        else:
            recommendations.append("Block is complete; ready for assembly.")
        return {"block_id": block_id, "scene": b["scene_title"], "state": state, "warnings": warnings, "recommendations": recommendations}

    def project_report(self) -> dict:
        state = compute_project_state(self.db)
        blocks = [self.analyze_block(s["block_id"]) for s in state["states"]]
        next_actions = []
        for item in blocks:
            rec = item["recommendations"]
            if rec:
                next_actions.append({"block_id": item["block_id"], "action": rec[0]})
        return {"project_state": state, "blocks": blocks, "next_actions": next_actions[:20]}

    def export_report(self) -> Path:
        out = self.db.root_dir / "production_reports"
        out.mkdir(parents=True, exist_ok=True)
        path = out / "v24_director_report.json"
        path.write_text(json.dumps(self.project_report(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path
