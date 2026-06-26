"""Create/replace a project from a script plan."""
from __future__ import annotations
import json, re
from pathlib import Path
from hps.local_ai.script_splitter import qwen_plan, deterministic_plan
from hps.core.asset_library import save_style_bible, register_assets_from_plan, inject_style

SAFE = re.compile(r"[^a-zA-Z0-9_\-]+")

def _id(s, default):
    s = SAFE.sub("_", str(s or "").strip().lower()).strip("_")
    return s or default

def _esc_id(prefix, n): return f"{prefix}_{n:03d}"

class ScriptImporter:
    def __init__(self, db):
        self.db = db

    def build_plan(self, script: str, title: str, use_qwen: bool = True, model: str = "qwen2.5:7b", host: str = "http://127.0.0.1:11434"):
        if use_qwen:
            return qwen_plan(script, title, model=model, host=host)[0]
        return deterministic_plan(script, title)

    def apply_plan(self, plan: dict, replace_existing: bool = True):
        project_id = self.db.project_id() or "project"
        title = plan.get("title") or "Historical POV Project"
        self.db.upsert_project(project_id, title, runtime_target="auto")
        if replace_existing:
            for tbl in ["audio_versions", "exports", "production_jobs", "blocks", "scenes", "characters", "voice_states"]:
                try: self.db.execute(f"DELETE FROM {tbl}")
                except Exception: pass
        self.db.execute("INSERT OR IGNORE INTO voice_states(id, project_id, delivery_prompt) VALUES (?,?,?)", ("narrator_slow", project_id, "Slow immersive historical POV narration; restrained, tired, human."))
        chars = plan.get("characters") or [{"id":"narrator", "role":"POV narrator", "baseline":"Listener-character"}]
        for c in chars:
            cid = _id(c.get("id") or c.get("name"), "narrator")
            self.db.execute("INSERT OR REPLACE INTO characters(id, project_id, role, actor_voice_id, baseline, notes) VALUES (?,?,?,?,?,?)",
                (cid, project_id, c.get("role",""), "", c.get("baseline",""), json.dumps(c, ensure_ascii=False)))
        save_style_bible(self.db, plan.get("style_bible") or {})
        register_assets_from_plan(self.db, plan)
        block_count = 0
        scenes = plan.get("scenes") or []
        for si, sc in enumerate(scenes, 1):
            sid = _id(sc.get("id"), _esc_id("scene", si))
            self.db.execute("INSERT OR REPLACE INTO scenes(id, project_id, title, summary, visual_theme, music_profile, sfx_profile, sort_order) VALUES (?,?,?,?,?,?,?,?)",
                (sid, project_id, sc.get("title") or f"Scene {si:03d}", sc.get("summary",""), sc.get("visual_theme",""), sc.get("music_profile",""), sc.get("sfx_profile",""), si))
            for bi, b in enumerate(sc.get("blocks") or [], 1):
                block_count += 1
                bid = _id(b.get("id"), _esc_id("block", block_count))
                chars_for = b.get("characters") or [chars[0].get("id","narrator")]
                char_id = _id(chars_for[0] if chars_for else "narrator", "narrator")
                image_prompt = inject_style(self.db, b.get("image_prompt") or "historical POV cinematic realism")
                music_cue = b.get("music_cue") or (sc.get("music_profile") or "local/imported ambient bed")
                notes = {"voice": b.get("voice", {}), "duration_seconds": b.get("duration_seconds"), "locations": b.get("locations", []), "equipment": b.get("equipment", [])}
                self.db.execute("""INSERT OR REPLACE INTO blocks(id, project_id, scene_id, character_id, voice_state_id, scene_label, text, status, issue, notes, image_prompt, music_cue, sort_order)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (bid, project_id, sid, char_id, "narrator_slow", b.get("scene_label") or f"Block {block_count:03d}", b.get("text",""), "missing", "", json.dumps(notes, ensure_ascii=False), image_prompt, music_cue, block_count))
        out = self.db.root_dir / "production" / "script_plan_latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"scenes": len(scenes), "blocks": block_count, "path": out, "source": plan.get("source", "unknown")}
