"""Local asset library + style bible persistence."""
from __future__ import annotations
import json, re
from pathlib import Path

SAFE = re.compile(r"[^a-zA-Z0-9_\-]+")

def _slug(s: str, default: str = "asset") -> str:
    s = SAFE.sub("_", (s or "").strip().lower()).strip("_")
    return s or default

def asset_dir(db) -> Path:
    p = db.root_dir / "assets" / "library"
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

def save_style_bible(db, style: dict):
    db.set_production_setting("style_bible_json", json.dumps(style or {}, ensure_ascii=False))
    return save_json(db.root_dir / "production" / "style_bible.json", style or {})

def load_style_bible(db) -> dict:
    raw = db.get_production_setting("style_bible_json", "{}")
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}

def register_assets_from_plan(db, plan: dict):
    base = asset_dir(db)
    chars = plan.get("characters") or []
    for c in chars:
        cid = _slug(c.get("id") or c.get("name") or "character")
        save_json(base / "characters" / f"{cid}.json", c)
    tags = {"locations": set(), "equipment": set()}
    for sc in plan.get("scenes", []):
        for b in sc.get("blocks", []):
            for loc in b.get("locations", []) or []: tags["locations"].add(str(loc))
            for eq in b.get("equipment", []) or []: tags["equipment"].add(str(eq))
    for kind, values in tags.items():
        for v in sorted(values):
            sid = _slug(v, kind[:-1])
            save_json(base / kind / f"{sid}.json", {"id": sid, "name": v, "source":"script_plan"})
    save_json(base / "asset_index.json", {"characters": chars, "locations": sorted(tags["locations"]), "equipment": sorted(tags["equipment"])})

def inject_style(db, prompt: str) -> str:
    style = load_style_bible(db)
    parts = [prompt or ""]
    for key in ["visual_style", "camera", "lighting"]:
        if style.get(key): parts.append(str(style[key]))
    if style.get("negative_prompt"):
        parts.append("NEGATIVE: " + str(style["negative_prompt"]))
    return ", ".join(p for p in parts if p)
