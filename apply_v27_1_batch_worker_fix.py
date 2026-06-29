from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------- safer production_queues.py ----------
pq = ROOT / "hps" / "core" / "production_queues.py"
pq.write_text(r'''
from __future__ import annotations

import json, re
from pathlib import Path
from hps.core.voice_pipeline import generate_voice_for_block

def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "asset")).strip("_").lower()

def _get(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default

def project_dir(db) -> Path:
    return Path(str(db.path)).parent

def ensure_character_library(db) -> Path:
    root = project_dir(db)
    path = root / "production" / "character_library.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    chars = {}
    for b in db.blocks():
        ch = str(_get(b, "character", _get(b, "character_id", "Narrator")))
        chars.setdefault(_safe(ch), {
            "name": ch,
            "voice_provider": "mock",
            "voice_preset": "narrator_slow",
            "delivery": "Slow immersive historical POV narration; restrained, tired, human.",
            "image_continuity": "Keep character visually consistent."
        })
    path.write_text(json.dumps(chars, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

def _status(db, bid, asset_type):
    try:
        b = db.block(bid)
        return _get(b, f"{asset_type}_status", _get(b, asset_type, "missing")) or "missing"
    except Exception:
        return "missing"

def _set_asset(db, bid, asset_type, path, status="generated"):
    try:
        db.set_block_asset(bid, asset_type, str(path), status)
        return
    except Exception:
        pass
    col = f"{asset_type}_status"
    try:
        db.execute(f"UPDATE blocks SET {col}=? WHERE id=?", (status, bid))
    except Exception:
        pass

def generate_missing_voices(db, provider="mock", limit=None, progress=None):
    ensure_character_library(db)
    done = []
    blocks = list(db.blocks())
    for i, b in enumerate(blocks, 1):
        bid = _get(b, "id")
        if not bid:
            continue
        if _status(db, bid, "voice") == "generated":
            continue
        if progress:
            progress("voice", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_voice_for_block(db, bid, provider=provider))
        if limit and len(done) >= limit:
            break
    return done

def generate_mock_image_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")
    char = _get(b, "character", _get(b, "character_id", "Narrator"))
    prompt = _get(b, "image_prompt", f"Image prompt for {block_id}")
    out = project_dir(db) / "assets" / "images" / f"{block_id}_{_safe(char)}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "MOCK IMAGE PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\nCHARACTER: {char}\n\nPROMPT:\n{prompt}\n",
        encoding="utf-8"
    )
    _set_asset(db, block_id, "image", out, "generated")
    return {"block_id": block_id, "image_path": str(out)}

def generate_missing_images(db, limit=None, progress=None):
    done = []
    blocks = list(db.blocks())
    for b in blocks:
        bid = _get(b, "id")
        if not bid:
            continue
        if _status(db, bid, "image") == "generated":
            continue
        if progress:
            progress("image", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_mock_image_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done

def generate_mock_music_for_block(db, block_id: str):
    b = db.block(block_id)
    if not b:
        raise RuntimeError(f"Block not found: {block_id}")
    char = _get(b, "character", _get(b, "character_id", "Narrator"))
    cue = _get(b, "music_cue", f"Music cue for {block_id}")
    out = project_dir(db) / "assets" / "music" / f"{block_id}_music.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "MOCK MUSIC PLACEHOLDER\n\n"
        f"BLOCK: {block_id}\nCHARACTER: {char}\n\nCUE:\n{cue}\n",
        encoding="utf-8"
    )
    _set_asset(db, block_id, "music", out, "generated")
    return {"block_id": block_id, "music_path": str(out)}

def generate_missing_music(db, limit=None, progress=None):
    done = []
    blocks = list(db.blocks())
    for b in blocks:
        bid = _get(b, "id")
        if not bid:
            continue
        if _status(db, bid, "music") == "generated":
            continue
        if progress:
            progress("music", bid, len(done) + 1, limit or len(blocks))
        done.append(generate_mock_music_for_block(db, bid))
        if limit and len(done) >= limit:
            break
    return done
''', encoding="utf-8")


# ---------- safer batch_production.py ----------
bp = ROOT / "hps" / "core" / "batch_production.py"
bp.write_text(r'''
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from hps.core.production_queues import ensure_character_library, generate_missing_voices, generate_missing_images, generate_missing_music

def _project_dir(db) -> Path:
    return Path(str(db.path)).parent

def _get(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default

def _write_report(db, report: dict) -> Path:
    out = _project_dir(db) / "production"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "batch_report_latest.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

def _count_status(db):
    blocks = list(db.blocks())
    total = len(blocks)
    def count(asset):
        n = 0
        for b in blocks:
            v = _get(b, f"{asset}_status", _get(b, asset, "missing"))
            if v == "generated":
                n += 1
        return n
    return {
        "total_blocks": total,
        "voice_generated": count("voice"),
        "image_generated": count("image"),
        "music_generated": count("music"),
    }

def run_batch_production(db, provider="mock", generate_voice=True, generate_images=True, generate_music=True, limit=None, progress=None):
    ensure_character_library(db)
    report = {
        "started": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "limit": limit,
        "steps": [],
        "before": _count_status(db),
    }

    if generate_voice:
        items = generate_missing_voices(db, provider=provider, limit=limit, progress=progress)
        report["steps"].append({"step": "voices", "generated": len(items), "items": items})

    if generate_images:
        items = generate_missing_images(db, limit=limit, progress=progress)
        report["steps"].append({"step": "images", "generated": len(items), "items": items})

    if generate_music:
        items = generate_missing_music(db, limit=limit, progress=progress)
        report["steps"].append({"step": "music", "generated": len(items), "items": items})

    report["after"] = _count_status(db)
    report["finished"] = datetime.now().isoformat(timespec="seconds")
    path = _write_report(db, report)
    report["report_path"] = str(path)
    return report
''', encoding="utf-8")


# ---------- patch studio_qt.py with progress + no freeze ----------
studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

if "QProgressDialog" not in s:
    s = s.replace("QInputDialog", "QInputDialog,QProgressDialog")

if "QTimer" not in s:
    s = s.replace("from PySide6.QtCore import Qt", "from PySide6.QtCore import Qt,QTimer")

if "from hps.core.batch_production import run_batch_production" not in s:
    s = s.replace(
        "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel",
        "from hps_qt.widgets.v24_orchestrator_panel import V24OrchestratorPanel\nfrom hps.core.batch_production import run_batch_production"
    )

# Replace current v27 method if present
start = s.find("def v27_generate_missing_assets(self):")
if start != -1:
    end = s.find("\n    def build_episode(self):", start)
    if end == -1:
        raise RuntimeError("Could not find end of v27 method")
    new_method = '''def v27_generate_missing_assets(self):
        if not self.db:
            return

        limit, ok = QInputDialog.getInt(
            self,
            "Batch Production",
            "How many missing blocks per asset type? 0 = ALL",
            5,
            0,
            100000,
            1
        )
        if not ok:
            return

        provider = self.provider_box.currentText()
        real_limit = None if limit == 0 else limit

        progress = QProgressDialog("Starting batch production...", "Cancel", 0, max(1, (real_limit or len(self.db.blocks())) * 3), self)
        progress.setWindowTitle("Batch Production")
        progress.setMinimumDuration(0)
        progress.setValue(0)

        counter = {"n": 0}

        def progress_cb(asset_type, block_id, i, total):
            counter["n"] += 1
            progress.setLabelText(f"{asset_type}: {block_id}")
            progress.setValue(counter["n"])
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("Batch production cancelled by user.")

        try:
            report = run_batch_production(
                self.db,
                provider=provider,
                generate_voice=True,
                generate_images=True,
                generate_music=True,
                limit=real_limit,
                progress=progress_cb,
            )
            progress.setValue(progress.maximum())

            lines = [f"{step['step']}: {step['generated']}" for step in report["steps"]]
            QMessageBox.information(
                self,
                "Batch Production Complete",
                "Generated:\\n" + "\\n".join(lines) + f"\\n\\nReport:\\n{report['report_path']}"
            )

            self.refresh_production_ui()

        except Exception as e:
            QMessageBox.critical(self, "Batch Production Failed", str(e))
        finally:
            progress.close()

    '''
    s = s[:start] + new_method + s[end+1:]

studio.write_text(s, encoding="utf-8")

print("V27.1 batch worker/progress/key fix applied.")