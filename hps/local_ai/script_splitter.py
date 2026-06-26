"""Full-script to production plan splitter.
Free-first: optionally uses local Qwen/Ollama; falls back to deterministic splitting.
"""
from __future__ import annotations
import json, re, math
from dataclasses import dataclass
from typing import Any
from hps.local_ai.ollama_client import OllamaClient

SYSTEM = """You are the LOCAL production director for Historical POV Studio.
Return valid JSON only. Do not call paid APIs. Do not invent major historical events.
Split narration into production scenes/blocks for a slow immersive historical POV video.
Each block should be a voiceover segment suitable for one image/timeline unit.
"""

PROMPT_TEMPLATE = """Create a production plan JSON for this script.
Requirements:
- JSON only, no markdown.
- Preserve the exact narration meaning; do not rewrite into a different story.
- Keep blocks roughly 80-180 words when possible.
- Use first-person sensory image prompts.
- Music is local/imported only: provide mood/intensity cue, not a paid music generation instruction.
- Voice is the only paid/API step: provide emotion/pace/pause cues.
- Include character/location/equipment tags for local asset library.

Schema:
{{
  "title": "short project title",
  "style_bible": {{"visual_style":"...", "camera":"...", "lighting":"...", "negative_prompt":"..."}},
  "characters": [{{"id":"narrator", "role":"POV narrator", "baseline":"..."}}],
  "scenes": [{{
    "id":"scene_001", "title":"...", "summary":"...", "visual_theme":"...", "music_profile":"...",
    "blocks":[{{
      "id":"block_001", "text":"exact narration segment", "scene_label":"...",
      "voice":{{"emotion":"...", "pace":"...", "pause_after":0.5}},
      "image_prompt":"cinematic realistic prompt", "music_cue":"local music cue", "duration_seconds":20,
      "characters":["narrator"], "locations":["..."], "equipment":["..."]
    }}]
  }}]
}}

SCRIPT:
{script}
"""

def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        return text[a:b+1]
    return text

def _words(text: str):
    return re.findall(r"\S+", text or "")

def _sentences(text: str) -> list[str]:
    # keep punctuation; split on sentence boundaries and paragraph breaks
    parts = re.split(r"(?<=[.!?])\s+|\n\s*\n+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]

def deterministic_plan(script: str, title: str = "Historical POV Project", target_words: int = 135) -> dict[str, Any]:
    sentences = _sentences(script)
    if not sentences:
        sentences = [script.strip()] if script.strip() else []
    blocks = []
    cur = []
    count = 0
    for s in sentences:
        wc = len(_words(s))
        if cur and count + wc > target_words:
            blocks.append(" ".join(cur).strip())
            cur, count = [], 0
        cur.append(s); count += wc
    if cur:
        blocks.append(" ".join(cur).strip())
    if not blocks and script.strip():
        blocks = [script.strip()]

    scenes = []
    block_no = 1
    for scene_no in range(1, math.ceil(len(blocks)/5)+1):
        scene_blocks = blocks[(scene_no-1)*5:scene_no*5]
        items = []
        for text in scene_blocks:
            bid = f"block_{block_no:03d}"
            words = len(_words(text))
            items.append({
                "id": bid,
                "text": text,
                "scene_label": f"Segment {block_no:03d}",
                "voice": {"emotion":"immersive, restrained", "pace":"slow", "pause_after":0.5},
                "image_prompt": "first-person historical POV, cinematic realism, natural light, historically accurate clothing and equipment, no fantasy elements; narration moment: " + text[:220],
                "music_cue": "local/imported low cinematic bed, subtle tension, no melody overpowering narration",
                "duration_seconds": max(8, int(words / 2.15)),
                "characters": ["narrator"], "locations": [], "equipment": []
            })
            block_no += 1
        scenes.append({
            "id": f"scene_{scene_no:03d}",
            "title": f"Scene {scene_no:03d}",
            "summary": scene_blocks[0][:220] if scene_blocks else "",
            "visual_theme": "cinematic historical realism, first-person sensory POV",
            "music_profile": "local/imported ambient bed; no paid music generation",
            "sfx_profile": "optional local SFX only",
            "blocks": items,
        })
    return {
        "title": title or "Historical POV Project",
        "style_bible": {
            "visual_style": "cinematic historical realism, immersive first-person POV, grounded details",
            "camera": "35mm documentary still, eye-level POV, shallow depth of field only when natural",
            "lighting": "natural practical light, smoke/dust/haze where appropriate",
            "negative_prompt": "fantasy armor, anachronistic weapons, modern objects, text, watermark, extra fingers"
        },
        "characters": [{"id":"narrator", "role":"POV narrator", "baseline":"Listener-character; historically plausible clothing, equipment and condition."}],
        "scenes": scenes,
        "source": "deterministic_fallback"
    }

def qwen_plan(script: str, title: str, model: str = "qwen2.5:7b", host: str = "http://127.0.0.1:11434") -> tuple[dict[str, Any], str]:
    client = OllamaClient(model=model, host=host, timeout=240)
    prompt = PROMPT_TEMPLATE.format(script=script[:45000])
    res = client.generate(prompt, system=SYSTEM, temperature=0.15)
    if not res.ok:
        plan = deterministic_plan(script, title)
        plan["source"] = "deterministic_fallback_ollama_unavailable"
        plan["ollama_error"] = res.error
        return plan, res.error
    try:
        plan = json.loads(_clean_json(res.text))
        if not isinstance(plan, dict) or not plan.get("scenes"):
            raise ValueError("JSON missing scenes")
        plan.setdefault("title", title or "Historical POV Project")
        plan["source"] = f"ollama:{model}"
        return plan, ""
    except Exception as exc:
        plan = deterministic_plan(script, title)
        plan["source"] = "deterministic_fallback_bad_json"
        plan["ollama_error"] = f"{exc}"
        plan["ollama_raw_preview"] = res.text[:2000]
        return plan, str(exc)
