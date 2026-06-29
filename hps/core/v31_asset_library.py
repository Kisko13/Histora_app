from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.block_state import approved_voice_path
from hps.core.scene_music_plan import create_scene_music_plan
from hps.core.visual_slot_plan import create_visual_slot_plan
from hps.core.v29_asset_managers import SceneMusicManager, VisualSlotManager, project_dir

IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".txt"]
MUSIC_EXTS = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".txt"]


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ""
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _first_asset(folder: Path, names: list[str], exts: list[str]) -> Path | None:
    if not folder.exists():
        return None
    for n in names:
        p = folder / n
        if p.exists() and p.is_file():
            return p
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in exts and not p.name.endswith("metadata.json"):
            return p
    return None


class V31AssetLibrary:
    """Canonical V31 asset library.

    Voice remains block based.
    Visuals are episode-level visual slots.
    Music is scene-level.

    This class makes the generated plans executable by ensuring every planned slot/scene
    has a real folder, metadata, prompt file, import instructions, and a safe placeholder
    asset when no approved real asset exists yet. The placeholder is deliberately a .txt
    file so it never pretends to be a final image/audio file, but the timeline and preview
    can still run end-to-end.
    """

    def __init__(self, db):
        self.db = db
        self.root = project_dir(db)
        self.production_dir = self.root / "production"
        self.assets_dir = self.root / "assets"
        self.visual_manager = VisualSlotManager(db)
        self.music_manager = SceneMusicManager(db)

    def normalize(self, visual_slots: int = 15, create_placeholders: bool = True) -> dict:
        self.production_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        visual_plan_path = self.production_dir / "visual_slot_plan.json"
        music_plan_path = self.production_dir / "scene_music_plan.json"
        if not visual_plan_path.exists():
            create_visual_slot_plan(self.db, slot_count=visual_slots)
        if not music_plan_path.exists():
            create_scene_music_plan(self.db)

        visual_report = self._normalize_visual_slots(create_placeholders=create_placeholders)
        music_report = self._normalize_scene_music(create_placeholders=create_placeholders)
        voice_report = self._scan_voice_assets()

        report = {
            "version": "v31_asset_library",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "policy": {
                "voice": "block_based",
                "visuals": "visual_slot_based_10_to_20_total_images",
                "music": "scene_based",
                "placeholders": "txt placeholders enable planning/preview but do not represent final media",
            },
            "voice": voice_report,
            "visual_slots": visual_report,
            "scene_music": music_report,
        }
        out = self.production_dir / "asset_library.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["asset_library_path"] = str(out)
        return report

    def _normalize_visual_slots(self, create_placeholders: bool) -> dict:
        plan = self.visual_manager.load_plan()
        slots = plan.get("slots", [])
        root_dir = self.assets_dir / "visual_slots"
        root_dir.mkdir(parents=True, exist_ok=True)

        normalized = []
        for slot in slots:
            sid = slot.get("id") or f"VIS{len(normalized)+1:03d}"
            slot["id"] = sid
            folder = root_dir / sid
            folder.mkdir(parents=True, exist_ok=True)

            prompt = slot.get("prompt", "")
            negative = slot.get("negative_prompt", "")
            (folder / "prompt.txt").write_text(prompt + "\n\nNEGATIVE:\n" + negative + "\n", encoding="utf-8")
            (folder / "README_ADD_IMAGE_HERE.txt").write_text(
                "Put the final image for this visual slot in this folder and name it approved.png.\n"
                "Accepted alternatives: approved.jpg, approved.webp, approved.txt.\n"
                "This slot can cover many narration blocks. Do NOT create one image per block unless you want to.\n",
                encoding="utf-8",
            )

            approved = self.visual_manager.find_approved_slot_asset(sid)
            if not approved and create_placeholders:
                approved = folder / "approved.txt"
                approved.write_text(
                    "V31 VISUAL SLOT PLACEHOLDER\n\n"
                    f"SLOT: {sid}\nTITLE: {slot.get('title', sid)}\n"
                    f"COVERS: {slot.get('start_block', '')} -> {slot.get('end_block', '')}\n"
                    f"DURATION: {slot.get('duration_seconds', 0)} sec\n\n"
                    "PROMPT:\n" + prompt + "\n\n"
                    "Replace this file with approved.png when the real image is ready.\n",
                    encoding="utf-8",
                )

            asset_rel = _rel(self.root, approved)
            slot["asset_path"] = asset_rel
            slot["status"] = "approved" if approved else "planned"

            metadata = {
                "slot_id": sid,
                "title": slot.get("title", sid),
                "status": slot.get("status", "planned"),
                "duration_seconds": slot.get("duration_seconds", 0),
                "start_block": slot.get("start_block", ""),
                "end_block": slot.get("end_block", ""),
                "block_ids": slot.get("block_ids", []),
                "scene_titles": slot.get("scene_titles", []),
                "characters": slot.get("characters", []),
                "prompt": prompt,
                "negative_prompt": negative,
                "asset_path": asset_rel,
            }
            (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

            # Compatibility pointers for older Block Workspace progress bars.
            for bid in slot.get("block_ids", []) or []:
                if not bid:
                    continue
                block_dir = self.assets_dir / "images" / bid
                block_dir.mkdir(parents=True, exist_ok=True)
                (block_dir / "approved.txt").write_text(
                    "V31 VISUAL SLOT POINTER — this block reuses an episode visual slot.\n\n"
                    f"BLOCK: {bid}\nSLOT: {sid}\nSLOT_ASSET: {asset_rel}\n",
                    encoding="utf-8",
                )
                try:
                    self.db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (bid,))
                except Exception:
                    pass

            normalized.append(metadata)

        self.visual_manager.save_plan(plan)
        return {
            "total": len(slots),
            "approved_or_placeholder": sum(1 for s in slots if s.get("asset_path")),
            "asset_root": _rel(self.root, root_dir),
            "slots": normalized,
        }

    def _normalize_scene_music(self, create_placeholders: bool) -> dict:
        plan = self.music_manager.load_plan()
        scenes = plan.get("scenes", [])
        root_dir = self.assets_dir / "scene_music"
        root_dir.mkdir(parents=True, exist_ok=True)

        normalized = []
        for scene in scenes:
            sid = scene.get("id") or f"scene_{len(normalized)+1:03d}"
            scene["id"] = sid
            folder = root_dir / sid
            folder.mkdir(parents=True, exist_ok=True)
            cue = scene.get("cue", "")
            (folder / "cue.txt").write_text(cue + "\n", encoding="utf-8")
            (folder / "README_ADD_MUSIC_HERE.txt").write_text(
                "Put the final music bed for this scene in this folder and name it approved.mp3.\n"
                "Accepted alternatives: approved.wav, approved.m4a, approved.txt.\n"
                "This one file can cover the whole scene. Do NOT create music per block unless you want to.\n",
                encoding="utf-8",
            )

            approved = self.music_manager.find_approved_scene_asset(sid)
            if not approved and create_placeholders:
                approved = folder / "approved.txt"
                approved.write_text(
                    "V31 SCENE MUSIC PLACEHOLDER\n\n"
                    f"SCENE: {sid}\nTITLE: {scene.get('title', sid)}\n"
                    f"DURATION: {scene.get('duration_seconds', 0)} sec\n\n"
                    "CUE:\n" + cue + "\n\n"
                    "Replace this file with approved.mp3 when the real music is ready.\n",
                    encoding="utf-8",
                )

            asset_rel = _rel(self.root, approved)
            scene["asset_path"] = asset_rel
            scene["status"] = "approved" if approved else "planned"

            metadata = {
                "scene_id": sid,
                "title": scene.get("title", sid),
                "status": scene.get("status", "planned"),
                "duration_seconds": scene.get("duration_seconds", 0),
                "block_ids": scene.get("block_ids", []),
                "cue": cue,
                "asset_path": asset_rel,
            }
            (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

            for bid in scene.get("block_ids", []) or []:
                if not bid:
                    continue
                block_dir = self.assets_dir / "music" / bid
                block_dir.mkdir(parents=True, exist_ok=True)
                (block_dir / "approved.txt").write_text(
                    "V31 SCENE MUSIC POINTER — this block reuses the scene music bed.\n\n"
                    f"BLOCK: {bid}\nSCENE: {sid}\nSCENE_MUSIC_ASSET: {asset_rel}\n",
                    encoding="utf-8",
                )
                try:
                    self.db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (bid,))
                except Exception:
                    pass

            normalized.append(metadata)

        self.music_manager.save_plan(plan)
        return {
            "total": len(scenes),
            "approved_or_placeholder": sum(1 for s in scenes if s.get("asset_path")),
            "asset_root": _rel(self.root, root_dir),
            "scenes": normalized,
        }

    def _scan_voice_assets(self) -> dict:
        blocks = list(self.db.blocks())
        rows = []
        for b in blocks:
            bid = _get(b, "id")
            voice = approved_voice_path(self.db, bid)
            rows.append({
                "block_id": bid,
                "character": _get(b, "character_id", _get(b, "character", "Narrator")),
                "voice_path": _rel(self.root, voice),
                "approved": bool(voice),
            })
        return {
            "total_blocks": len(blocks),
            "approved": sum(1 for r in rows if r["approved"]),
            "items": rows,
        }


def normalize_project_assets(db, visual_slots: int = 15, create_placeholders: bool = True) -> dict:
    return V31AssetLibrary(db).normalize(visual_slots=visual_slots, create_placeholders=create_placeholders)
