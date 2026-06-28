from pathlib import Path

ROOT = Path(__file__).resolve().parent

voice_core = ROOT / "hps" / "core" / "voice_pipeline.py"
voice_core.parent.mkdir(parents=True, exist_ok=True)

voice_core.write_text(r'''
from __future__ import annotations

import json
import re
import wave
import struct
import math
from pathlib import Path


TAG_RE = re.compile(r"(?m)^\s*\[[A-Za-z0-9 _.'-]+(?:\|[^\]]+)?\]\s*$")


def clean_voice_text(text: str) -> str:
    text = text or ""
    text = TAG_RE.sub("", text)
    text = text.replace("ENDOFSCRIPT", "")
    text = re.sub(r"(?m)^echo\s+[\"']?Done[\"']?\s*$", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def assert_voice_text_safe(text: str):
    if TAG_RE.search(text or ""):
        raise RuntimeError("Voice text still contains speaker tags. Refusing paid voice generation.")
    if not (text or "").strip():
        raise RuntimeError("Voice text is empty.")


def make_mock_wav(path: Path, seconds: float = 1.0, freq: float = 440.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 22050
    frames = int(rate * seconds)

    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)

        for i in range(frames):
            value = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", value))


def save_voice_request(path: Path, block_id: str, character: str, provider: str, text: str):
    request = {
        "block_id": block_id,
        "character": character,
        "provider": provider,
        "voice_text": text,
        "paid_step": provider.lower() not in {"mock", "local_mock"},
        "speaker_tags_removed": True,
    }
    json_path = path.with_name(path.stem + "_voice_request.json")
    json_path.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_voice_for_block(db, block_id: str, provider: str = "mock") -> dict:
    block = db.block(block_id)
    if not block:
        raise RuntimeError(f"Block not found: {block_id}")

    raw_text = block["text"] if "text" in block.keys() else ""
    clean_text = clean_voice_text(raw_text)
    assert_voice_text_safe(clean_text)

    character = block["character"] if "character" in block.keys() else "Narrator"

    project_path = Path(str(db.path))
    voice_dir = project_path.parent / "voices"
    voice_dir.mkdir(parents=True, exist_ok=True)

    safe_character = re.sub(r"[^A-Za-z0-9_-]+", "_", str(character)).strip("_").lower() or "narrator"
    audio_path = voice_dir / f"{block_id}_{safe_character}.wav"

    if provider.lower() in {"mock", "local_mock"}:
        make_mock_wav(audio_path, seconds=min(3.0, max(0.8, len(clean_text.split()) / 4)))
    else:
        # Real provider integration belongs here.
        # For now refuse unless existing provider code calls this module explicitly.
        raise RuntimeError(
            f"Provider '{provider}' is not connected in V26 voice pipeline yet. "
            "Use provider=mock for safety testing."
        )

    save_voice_request(audio_path, block_id, character, provider, clean_text)

    try:
        db.set_block_asset(block_id, "voice", str(audio_path), "generated")
    except Exception:
        try:
            db.update_block_asset(block_id, "voice", str(audio_path), "generated")
        except Exception:
            pass

    return {
        "block_id": block_id,
        "character": character,
        "provider": provider,
        "audio_path": str(audio_path),
        "voice_text": clean_text,
    }
''', encoding="utf-8")


# Patch studio_qt.py button handler to use new voice pipeline.
studio = ROOT / "studio_qt.py"
s = studio.read_text(encoding="utf-8")

if "from hps.core.voice_pipeline import generate_voice_for_block" not in s:
    # put after other hps imports
    marker = "from hps.core.cost_control import cost_guard\n"
    if marker in s:
        s = s.replace(marker, marker + "from hps.core.voice_pipeline import generate_voice_for_block\n")
    else:
        s = "from hps.core.voice_pipeline import generate_voice_for_block\n" + s

# Replace old generate voice method if identifiable.
# If not, add a safe method and wire obvious button call names.
if "def generate_current_voice_v26" not in s:
    insert_at = s.find("    def current_cost_info(self):")
    if insert_at == -1:
        insert_at = s.find("    def auto_select_first_block(self):")

    method = r'''
    def generate_current_voice_v26(self):
        if not self.db or not self.selected_block_id:
            QMessageBox.warning(self, "No block selected", "Select a block first.")
            return

        provider = self.provider_box.currentText() if hasattr(self, "provider_box") else "mock"

        try:
            result = generate_voice_for_block(self.db, self.selected_block_id, provider=provider)
            QMessageBox.information(
                self,
                "Voice Generated",
                f"Generated voice for {result['block_id']}.\n\n"
                f"Character: {result['character']}\n"
                f"File: {result['audio_path']}\n\n"
                f"Clean text was saved in voice_request.json."
            )
            self.refresh_all()
            self.select_block(self.selected_block_id)
        except Exception as exc:
            QMessageBox.critical(self, "Voice generation failed", str(exc))

'''
    if insert_at != -1:
        s = s[:insert_at] + method + s[insert_at:]

# Wire common button callback names to the new method.
replacements = {
    "self.generate_voice": "self.generate_current_voice_v26",
    "self.generate_voice_clicked": "self.generate_current_voice_v26",
    "self.on_generate_voice": "self.generate_current_voice_v26",
}

# Avoid destructive mass replacement of definitions; only replace clicked.connect references.
for old, new in replacements.items():
    s = s.replace(f".clicked.connect({old})", f".clicked.connect({new})")

studio.write_text(s, encoding="utf-8")


# Patch BlockWorkspace if it owns Generate Voice button
for p in (ROOT / "hps_qt").rglob("*.py"):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    old_txt = txt

    if "Generate Voice" in txt and "generate_current_voice_v26" not in txt:
        # If widget emits/calls parent methods, try to route to main window method.
        txt = txt.replace(
            ".clicked.connect(self.generate_voice)",
            ".clicked.connect(lambda: self.window().generate_current_voice_v26())"
        )
        txt = txt.replace(
            ".clicked.connect(self.on_generate_voice)",
            ".clicked.connect(lambda: self.window().generate_current_voice_v26())"
        )
        txt = txt.replace(
            ".clicked.connect(self.generate_voice_clicked)",
            ".clicked.connect(lambda: self.window().generate_current_voice_v26())"
        )

    if txt != old_txt:
        p.write_text(txt, encoding="utf-8")


doc = ROOT / "docs" / "V26_COMPLETE_VOICE_PIPELINE.md"
doc.write_text("""# V26 Complete Voice Pipeline

Adds end-to-end clean voice generation safety.

When Generate Voice runs:

1. Reads selected block text.
2. Removes speaker tags like `[Marcus]`.
3. Refuses generation if tags remain.
4. Generates mock `.wav` for provider `mock`.
5. Saves an audit file beside the audio:

`B0001_marcus_voice_request.json`

The JSON contains the exact clean text sent to voice generation.

Real paid providers should be connected through `hps/core/voice_pipeline.py` so all paid voice generation passes through the same safety checks.
""", encoding="utf-8")

print("V26 complete voice pipeline installed.")
print("Run: .\\run_studio_v24.bat")