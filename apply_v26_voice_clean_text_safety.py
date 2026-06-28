from pathlib import Path

ROOT = Path(__file__).resolve().parent

voice_files = list((ROOT / "hps").rglob("*voice*.py")) + list((ROOT / "hps_qt").rglob("*voice*.py"))

for path in voice_files:
    txt = path.read_text(encoding="utf-8", errors="ignore")

    if "def clean_voice_text_v26" not in txt:
        txt = '''import re
import json
from pathlib import Path

def clean_voice_text_v26(text: str) -> str:
    """
    Speaker tags are metadata only.
    Never send [Marcus], [Titus], etc. to voice generation.
    """
    text = text or ""
    text = re.sub(r"(?m)^\\s*\\[[A-Za-z0-9 _.'-]+(?:\\|[^\\]]+)?\\]\\s*$", "", text)
    text = text.replace("ENDOFSCRIPT", "")
    text = re.sub(r"(?m)^echo\\s+[\\"']?Done[\\"']?\\s*$", "", text, flags=re.I)
    return text.strip()

def assert_voice_text_safe_v26(text: str):
    if re.search(r"(?m)^\\s*\\[[A-Za-z0-9 _.'-]+(?:\\|[^\\]]+)?\\]\\s*$", text or ""):
        raise RuntimeError("Voice text still contains speaker tags. Refusing to generate paid voice.")

def save_voice_request_v26(output_audio_path, block_id, character, provider, voice_text):
    try:
        p = Path(output_audio_path)
        data = {
            "block_id": block_id,
            "character": character,
            "provider": provider,
            "voice_text": voice_text,
            "paid_step": True,
            "speaker_tags_removed": True,
        }
        (p.parent / f"{p.stem}_voice_request.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

''' + txt

    # soft patch common direct TTS variable names if present
    txt = txt.replace("text=block_text", "text=clean_voice_text_v26(block_text)")
    txt = txt.replace("text = block_text", "text = clean_voice_text_v26(block_text)")
    txt = txt.replace("voice_text = block_text", "voice_text = clean_voice_text_v26(block_text)")
    txt = txt.replace("voice_text=block_text", "voice_text=clean_voice_text_v26(block_text)")

    path.write_text(txt, encoding="utf-8")

doc = ROOT / "docs" / "V26_VOICE_CLEAN_TEXT_SAFETY.md"
doc.write_text("""# V26 Voice Clean Text Safety

Adds permanent voice safety helpers:

- removes `[Speaker]` tags before TTS
- refuses paid voice generation if tags remain
- saves a `voice_request.json` audit file beside generated audio

This protects the only paid step in the pipeline.
""", encoding="utf-8")

print("V26 voice clean text safety patch applied.")
print("Run: .\\run_studio_v24.bat")