from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def project_dir(db) -> Path:
    return Path(str(db.path)).parent


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


class VisualSlotManager:
    """Episode-level visual manager. Images belong to visual slots, not blocks."""

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.plan_path = self.root / "production" / "visual_slot_plan.json"
        self.asset_root = self.root / "assets" / "visual_slots"

    def load_plan(self) -> dict:
        return load_json(self.plan_path, {"slots": []})

    def save_plan(self, plan: dict) -> Path:
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.plan_path

    def ensure_slot_folders(self) -> dict:
        plan = self.load_plan()
        slots = plan.get("slots", [])
        self.asset_root.mkdir(parents=True, exist_ok=True)
        for slot in slots:
            slot_id = slot.get("id") or f"VIS{len(slots)+1:03d}"
            slot_dir = self.asset_root / slot_id
            slot_dir.mkdir(parents=True, exist_ok=True)
            meta_path = slot_dir / "metadata.json"
            asset_path = slot.get("asset_path", "")
            approved = self.find_approved_slot_asset(slot_id)
            if approved:
                asset_path = str(approved.relative_to(self.root)).replace("\\", "/")
                slot["status"] = "approved"
            elif not slot.get("status"):
                slot["status"] = "planned"
            slot["asset_path"] = asset_path
            meta = {
                "slot_id": slot_id,
                "title": slot.get("title", slot_id),
                "status": slot.get("status", "planned"),
                "duration_seconds": slot.get("duration_seconds", 0),
                "start_block": slot.get("start_block", ""),
                "end_block": slot.get("end_block", ""),
                "block_ids": slot.get("block_ids", []),
                "prompt": slot.get("prompt", ""),
                "negative_prompt": slot.get("negative_prompt", ""),
                "asset_path": asset_path,
            }
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.save_plan(plan)
        return plan

    def find_approved_slot_asset(self, slot_id: str) -> Path | None:
        slot_dir = self.asset_root / slot_id
        if not slot_dir.exists():
            return None
        preferred = ["approved.png", "approved.jpg", "approved.jpeg", "approved.webp", "approved.txt"]
        for name in preferred:
            p = slot_dir / name
            if p.exists():
                return p
        for p in slot_dir.iterdir():
            if p.is_file() and p.stem.lower().startswith("approved"):
                return p
        return None

    def slot_for_block(self, block_id: str) -> dict | None:
        for slot in self.load_plan().get("slots", []):
            if block_id in (slot.get("block_ids") or []):
                return slot
        return None

    def approved_count(self) -> int:
        return sum(1 for s in self.load_plan().get("slots", []) if self.find_approved_slot_asset(s.get("id", "")))


class SceneMusicManager:
    """Scene-level music manager. Music belongs to scenes, not blocks."""

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.plan_path = self.root / "production" / "scene_music_plan.json"
        self.asset_root = self.root / "assets" / "scene_music"

    def load_plan(self) -> dict:
        return load_json(self.plan_path, {"scenes": []})

    def save_plan(self, plan: dict) -> Path:
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.plan_path

    def ensure_scene_folders(self) -> dict:
        plan = self.load_plan()
        scenes = plan.get("scenes", [])
        self.asset_root.mkdir(parents=True, exist_ok=True)
        for scene in scenes:
            sid = scene.get("id") or "scene"
            scene_dir = self.asset_root / sid
            scene_dir.mkdir(parents=True, exist_ok=True)
            approved = self.find_approved_scene_asset(sid)
            asset_path = scene.get("asset_path", "")
            if approved:
                asset_path = str(approved.relative_to(self.root)).replace("\\", "/")
                scene["status"] = "approved"
            elif not scene.get("status"):
                scene["status"] = "planned"
            scene["asset_path"] = asset_path
            meta = {
                "scene_id": sid,
                "title": scene.get("title", sid),
                "status": scene.get("status", "planned"),
                "duration_seconds": scene.get("duration_seconds", 0),
                "block_ids": scene.get("block_ids", []),
                "cue": scene.get("cue", ""),
                "asset_path": asset_path,
            }
            (scene_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.save_plan(plan)
        return plan

    def find_approved_scene_asset(self, scene_id: str) -> Path | None:
        scene_dir = self.asset_root / scene_id
        if not scene_dir.exists():
            return None
        preferred = ["approved.mp3", "approved.wav", "approved.m4a", "approved.aac", "approved.flac", "approved.txt"]
        for name in preferred:
            p = scene_dir / name
            if p.exists():
                return p
        for p in scene_dir.iterdir():
            if p.is_file() and p.stem.lower().startswith("approved"):
                return p
        return None

    def scene_for_block(self, block_id: str) -> dict | None:
        for scene in self.load_plan().get("scenes", []):
            if block_id in (scene.get("block_ids") or []):
                return scene
        row = self.db.scene_for_block(block_id)
        if row:
            return {"id": row["id"], "title": row["title"], "block_ids": [block_id]}
        return None

    def approved_count(self) -> int:
        return sum(1 for s in self.load_plan().get("scenes", []) if self.find_approved_scene_asset(s.get("id", "")))
