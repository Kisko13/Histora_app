from pathlib import Path

ROOT = Path(__file__).resolve().parent

pipeline = ROOT / "hps" / "core" / "production_queues.py"
pipeline.write_text(r'''
from __future__ import annotations

import json
import re
from pathlib import Path

from hps.core.voice_pipeline import generate_voice_for_block


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()


def block_rows(db):
    return db.blocks()


def project_dir(db) -> Path:
    return Path(str(db.path)).parent


def ensure_character_library(db) -> Path:
    root = project_dir(db)
    path = root / "production" / "character_library.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    chars = {}
    for b in db.blocks():
        ch = str(b["character"] if "character" in b.keys() else "Narrator")
        key = _safe(ch)
        chars.setdefault(key, {
            "name": ch,
            "voice_provider": "mock",
            "voice_preset": "narrator_slow",
            "delivery": "Slow immersive historical POV narration; restrained, tired, human.",
            "image_continuity": "Keep character visually consistent across all generated images.",
        })

    path.write_text(json.dumps(chars, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def generate_missing_voices(db, provider="mock", limit=None):
    ensure_character_library(db)
    done = []

    for b in db.blocks():
        bid = b["id"]
        voice_status = b["voice_status"] if "voice_status" in b.keys() else ""
        if voice_status == "generated":
            continue

        result = generate_voice_for_block(db, bid, provider=provider)
        done.append(result)

        if limit and len(done) >= limit:
            break

    return done


def generate_mock_image_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")

    root = project_dir(db)
    out = root / "assets" / "images" / f"{block_id}_{_safe(b['character'])}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    prompt = ""
    try:
        prompt = b["image_prompt"]
    except Exception:
        prompt = f"Image prompt for {block_id}"

    out.write_text(
        "MOCK IMAGE PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\n"
        f"CHARACTER: {b['character']}\n\n"
        f"PROMPT:\n{prompt}\n",
        encoding="utf-8"
    )

    try:
        db.set_block_asset(block_id, "image", str(out), "generated")
    except Exception:
        pass

    return {"block_id": block_id, "image_path": str(out)}


def generate_missing_images(db, limit=None):
    done = []
    for b in db.blocks():
        bid = b["id"]
        image_status = b["image_status"] if "image_status" in b.keys() else ""
        if image_status == "generated":
            continue
        done.append(generate_mock_image_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done


def generate_mock_music_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")

    root = project_dir(db)
    out = root / "assets" / "music" / f"{block_id}_music.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    cue = ""
    try:
        cue = b["music_cue"]
    except Exception:
        cue = f"Music cue for {block_id}"

    out.write_text(
        "MOCK MUSIC PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\n"
        f"CHARACTER: {b['character']}\n\n"
        f"CUE:\n{cue}\n",
        encoding="utf-8"
    )

    try:
        db.set_block_asset(block_id, "music", str(out), "generated")
    except Exception:
        pass

    return {"block_id": block_id, "music_path": str(out)}


def generate_missing_music(db, limit=None):
    done = []
    for b in db.blocks():
        bid = b["id"]
        music_status = b["music_status"] if "music_status" in b.keys() else ""
        if music_status == "generated":
            continue
        done.append(generate_mock_music_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done
''', encoding="utf-8")


studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

if "from hps.core.production_queues import" not in s:
    s = s.replace(
        "from hps.core.voice_pipeline import generate_voice_for_block\n",
        "from hps.core.voice_pipeline import generate_voice_for_block\n"
        "from hps.core.production_queues import ensure_character_library, generate_missing_voices, generate_missing_images, generate_missing_music\n"
    )

if "def v27_generate_missing_voices" not in s:
    insert_at = s.find("    def generate_current_voice_v26(self):")
    methods = r'''
    def v27_character_library(self):
        if not self.db:
            return
        path = ensure_character_library(self.db)
        QMessageBox.information(self, "Character Library", f"Character library saved:\n{path}")

    def v27_generate_missing_voices(self):
        if not self.db:
            return
        provider = self.provider_box.currentText() if hasattr(self, "provider_box") else "mock"
        done = generate_missing_voices(self.db, provider=provider)
        QMessageBox.information(self, "Voice Queue Complete", f"Generated {len(done)} voice file(s).")
        self.refresh_all()
        if self.selected_block_id:
            self.select_block(self.selected_block_id)

    def v27_generate_missing_images(self):
        if not self.db:
            return
        done = generate_missing_images(self.db)
        QMessageBox.information(self, "Image Queue Complete", f"Generated {len(done)} mock image placeholder(s).")
        self.refresh_all()
        if self.selected_block_id:
            self.select_block(self.selected_block_id)

    def v27_generate_missing_music(self):
        if not self.db:
            return
        done = generate_missing_music(self.db)
        QMessageBox.information(self, "Music Queue Complete", f"Generated {len(done)} mock music placeholder(s).")
        self.refresh_all()
        if self.selected_block_id:
            self.select_block(self.selected_block_id)

'''
    s = s[:insert_at] + methods + s[insert_at:]

# Add top toolbar buttons after existing Generate Voice if possible
if "Character Library" not in s:
    s = s.replace(
        '        self.voice_btn = QPushButton("Generate Voice")',
        '        self.voice_btn = QPushButton("Generate Voice")\n'
        '        self.charlib_btn = QPushButton("Character Library")\n'
        '        self.voice_queue_btn = QPushButton("Generate Missing Voices")\n'
        '        self.image_queue_btn = QPushButton("Generate Missing Images")\n'
        '        self.music_queue_btn = QPushButton("Generate Missing Music")'
    )

    s = s.replace(
        '        toolbar.addWidget(self.voice_btn)',
        '        toolbar.addWidget(self.voice_btn)\n'
        '        toolbar.addWidget(self.charlib_btn)\n'
        '        toolbar.addWidget(self.voice_queue_btn)\n'
        '        toolbar.addWidget(self.image_queue_btn)\n'
        '        toolbar.addWidget(self.music_queue_btn)'
    )

    s = s.replace(
        '        self.voice_btn.clicked.connect(self.generate_current_voice_v26)',
        '        self.voice_btn.clicked.connect(self.generate_current_voice_v26)\n'
        '        self.charlib_btn.clicked.connect(self.v27_character_library)\n'
        '        self.voice_queue_btn.clicked.connect(self.v27_generate_missing_voices)\n'
        '        self.image_queue_btn.clicked.connect(self.v27_generate_missing_images)\n'
        '        self.music_queue_btn.clicked.connect(self.v27_generate_missing_music)'
    )

studio.write_text(s, encoding="utf-8")

doc = ROOT / "docs" / "V27_PRODUCTION_QUEUES.md"
doc.write_text("""# V27 Production Queues

Adds:

1. Character Library
- creates `production/character_library.json`

2. Voice Queue
- Generate Missing Voices
- uses clean tagged-script voice pipeline
- mock provider writes audit files

3. Image Queue
- Generate Missing Images
- creates mock image prompt placeholder files

4. Music Queue
- Generate Missing Music
- creates mock music cue placeholder files

This is still offline/free except voice provider when switched away from mock.
""", encoding="utf-8")

print("V27 production queues installed.")
print("Run: .\\run_studio_v24.bat")