from pathlib import Path
import shutil

from hps.core.block_state import compute_project_state


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


class ProductionController:
    """
    v22 production controller.

    UI should ask this controller what the next task is and execute work through it.
    Widgets should not own production business logic.
    """

    def __init__(self, db):
        self.db = db

    def build_queue(self):
        project = compute_project_state(self.db)
        tasks = []
        for s in project["states"]:
            block_id = s["block_id"]
            scene = s["scene"]
            if not s["voice_ok"]:
                tasks.append({
                    "priority": 100,
                    "type": "voice",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Generate / approve voice",
                    "reason": "Voice is required before accurate timing.",
                })
            elif not s["image_ok"]:
                tasks.append({
                    "priority": 80,
                    "type": "image",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Import / approve image",
                    "reason": "Approved image is required for assembly.",
                })
            elif not s["music_ok"]:
                tasks.append({
                    "priority": 60,
                    "type": "music",
                    "block_id": block_id,
                    "scene": scene,
                    "action": "Import / approve music",
                    "reason": "Music/SFX is missing.",
                })

        if not tasks and project["assembly_ready"] == project["total"] and project["total"] > 0:
            tasks.append({
                "priority": 20,
                "type": "assembly",
                "block_id": "",
                "scene": "Episode",
                "action": "Refresh / export assembly",
                "reason": "All required assets are ready.",
            })

        tasks.sort(key=lambda t: -t["priority"])
        return tasks

    def next_task(self):
        q = self.build_queue()
        return q[0] if q else None

    def _next_numbered_path(self, folder: Path, ext: str):
        folder.mkdir(parents=True, exist_ok=True)
        nums = []
        for p in folder.glob("v*.*"):
            stem = p.stem.lower()
            if stem.startswith("v") and stem[1:].isdigit():
                nums.append(int(stem[1:]))
        n = max(nums) + 1 if nums else 1
        return folder / f"v{n:03d}{ext.lower()}"

    def import_image(self, block_id, source_path):
        source_path = Path(source_path)
        if source_path.suffix.lower() not in IMAGE_EXTS:
            raise ValueError("Unsupported image file.")
        folder = self.db.root_dir / "assets" / "images" / block_id
        dst = self._next_numbered_path(folder, source_path.suffix)
        shutil.copy2(source_path, dst)
        self.db.execute("UPDATE blocks SET image_status='generated' WHERE id=?", (block_id,))
        return dst

    def approve_image(self, block_id, image_path):
        image_path = Path(image_path)
        folder = self.db.root_dir / "assets" / "images" / block_id
        approved = folder / ("approved" + image_path.suffix.lower())
        shutil.copy2(image_path, approved)
        self.db.execute("UPDATE blocks SET image_status='approved' WHERE id=?", (block_id,))
        return approved

    def import_music(self, block_id, source_path):
        source_path = Path(source_path)
        if source_path.suffix.lower() not in AUDIO_EXTS:
            raise ValueError("Unsupported audio file.")
        folder = self.db.root_dir / "assets" / "music" / block_id
        dst = self._next_numbered_path(folder, source_path.suffix)
        shutil.copy2(source_path, dst)
        self.db.execute("UPDATE blocks SET music_status='generated' WHERE id=?", (block_id,))
        return dst

    def approve_music(self, block_id, audio_path):
        audio_path = Path(audio_path)
        folder = self.db.root_dir / "assets" / "music" / block_id
        approved = folder / ("approved" + audio_path.suffix.lower())
        shutil.copy2(audio_path, approved)
        self.db.execute("UPDATE blocks SET music_status='approved' WHERE id=?", (block_id,))
        return approved
