from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "hps" / "core" / "analysis"
PKG.mkdir(parents=True, exist_ok=True)

(PKG / "__init__.py").write_text("", encoding="utf-8")

(PKG / "models.py").write_text(r'''
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class AnalysisContext:
    project_title: str = "Historical POV Project"
    historical_period: str = ""
    main_pov_character: str = ""
    voice_style: str = ""
    target_runtime_minutes: int = 75
    known_characters: list[str] = field(default_factory=list)
    known_locations: list[str] = field(default_factory=list)
    known_equipment: list[str] = field(default_factory=list)
    style_bible: str = ""


@dataclass
class CharacterProfile:
    id: str
    name: str
    role: str = ""
    baseline: str = ""
    appears_in_scenes: list[str] = field(default_factory=list)


@dataclass
class ProductionBlock:
    id: str
    scene_id: str
    text: str
    character: str
    duration_seconds: int
    voice: dict[str, Any]
    image_prompt: str
    music_cue: str
    locations: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    sfx: list[str] = field(default_factory=list)
    ambience: list[str] = field(default_factory=list)


@dataclass
class ProductionScene:
    id: str
    title: str
    summary: str
    blocks: list[ProductionBlock] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)


@dataclass
class ProductionPlan:
    title: str
    source: str
    context: AnalysisContext
    characters: list[CharacterProfile]
    scenes: list[ProductionScene]
    style_bible: dict[str, str]
    production_policy: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
''', encoding="utf-8")


(PKG / "preprocessor.py").write_text(r'''
from __future__ import annotations
import re


def clean_script(script: str) -> str:
    text = (script or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "\n\n", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(script: str) -> list[str]:
    text = clean_script(script)
    return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def first_clean_sentence(text: str, max_len: int = 80) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    first = re.split(r"(?<=[.!?])\s+", t)[0] if t else ""
    if len(first) > max_len:
        first = first[:max_len].rsplit(" ", 1)[0]
    return first or "Untitled Scene"
''', encoding="utf-8")


(PKG / "deterministic.py").write_text(r'''
from __future__ import annotations
import re
from collections import Counter, defaultdict

from .models import (
    AnalysisContext, CharacterProfile, ProductionBlock,
    ProductionScene, ProductionPlan
)
from .preprocessor import split_paragraphs, word_count, first_clean_sentence


STOP_NAMES = {
    "The", "And", "But", "Then", "There", "This", "That", "Long", "Before",
    "After", "When", "Where", "What", "Why", "How", "Part", "Chapter",
    "Scene", "Production", "Script", "First", "Second", "Third"
}

LOCATION_WORDS = {
    "camp", "tent", "river", "road", "plain", "field", "battlefield", "city",
    "gate", "wall", "house", "farm", "forest", "sea", "ship", "hill", "valley",
    "village", "street", "fire", "ditch", "bridge", "mountain", "shore"
}

EQUIPMENT_WORDS = {
    "shield", "sword", "helmet", "armor", "spear", "bow", "arrow", "knife",
    "horse", "wagon", "boat", "rifle", "musket", "gun", "cloak", "boots",
    "torch", "drum", "trumpet", "standard", "banner"
}

SFX_WORDS = {
    "wind": "wind", "fire": "fire crackle", "water": "water", "river": "river",
    "horse": "horse", "horses": "horses", "scream": "scream", "screaming": "screams",
    "drum": "drums", "drums": "drums", "trumpet": "trumpet", "metal": "metal",
    "flies": "flies", "insects": "insects", "rain": "rain", "thunder": "thunder"
}


def detect_names(script: str, context: AnalysisContext) -> list[str]:
    names = set(context.known_characters or [])
    if context.main_pov_character:
        names.add(context.main_pov_character)

    candidates = re.findall(r"\b[A-Z][a-z]{2,}\b", script)
    counts = Counter(c for c in candidates if c not in STOP_NAMES)

    for name, count in counts.items():
        if count >= 2:
            names.add(name)

    if not names:
        names.add("Narrator")

    return sorted(names)


def detect_terms(text: str, base: set[str], known: list[str]) -> list[str]:
    low = text.lower()
    out = []
    for item in known:
        if item and item.lower() in low:
            out.append(item)
    for w in base:
        if re.search(rf"\b{re.escape(w)}\b", low):
            out.append(w)
    return sorted(set(out))


def detect_sfx(text: str) -> list[str]:
    low = text.lower()
    out = []
    for key, val in SFX_WORDS.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            out.append(val)
    return sorted(set(out))


def detect_emotion(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["battle", "blood", "scream", "kill", "weapon", "impact", "push"]):
        return "battle tension"
    if any(x in low for x in ["dead", "lost", "gone", "grief", "absence"]):
        return "grief"
    if any(x in low for x in ["night", "dark", "silence", "quiet", "waiting"]):
        return "dread"
    if any(x in low for x in ["home", "mother", "father", "remember", "child"]):
        return "memory"
    return "restrained"


def estimate_duration(text: str) -> int:
    return max(6, int(word_count(text) / 2.15) + 1)


def image_prompt(text: str, context: AnalysisContext, locations: list[str], equipment: list[str], character: str, emotion: str) -> str:
    moment = re.sub(r"\s+", " ", text.strip())[:260]
    loc = ", ".join(locations) if locations else "historically accurate environment"
    eq = ", ".join(equipment) if equipment else "period-correct clothing and props"
    period = context.historical_period or "historical setting"
    return (
        f"first-person immersive historical POV still, {period}, "
        f"character focus: {character}, location: {loc}, equipment/objects: {eq}, "
        f"emotion: {emotion}, cinematic realism, natural light, human-scale composition, "
        f"no fantasy, no modern objects, narration moment: {moment}"
    )


def music_cue(emotion: str, sfx: list[str]) -> str:
    return (
        f"local/imported music only, mood: {emotion}, "
        f"sfx suggestions: {', '.join(sfx) if sfx else 'none'}, keep under narration"
    )


def split_into_scene_chunks(paragraphs: list[str]) -> list[list[str]]:
    scenes = []
    current = []
    current_words = 0

    for p in paragraphs:
        wc = word_count(p)
        is_heading = wc <= 12 and not p.endswith(".")
        hard_transition = any(x in p.lower() for x in [
            "part one", "part two", "part three", "chapter", "afterward",
            "the next morning", "that night", "years later"
        ])

        if current and (current_words > 650 or hard_transition or is_heading):
            scenes.append(current)
            current = []
            current_words = 0

        if not is_heading:
            current.append(p)
            current_words += wc

    if current:
        scenes.append(current)

    return scenes


def split_blocks(scene_text: str, target_words: int = 130) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", scene_text.strip())
    blocks, cur, n = [], [], 0

    for s in sentences:
        wc = word_count(s)
        if cur and n + wc > target_words:
            blocks.append(" ".join(cur).strip())
            cur, n = [], 0
        cur.append(s)
        n += wc

    if cur:
        blocks.append(" ".join(cur).strip())

    return [b for b in blocks if b]


def analyze_deterministic(script: str, context: AnalysisContext) -> dict:
    paragraphs = split_paragraphs(script)
    names = detect_names(script, context)
    scene_chunks = split_into_scene_chunks(paragraphs)

    character_scene_map = defaultdict(list)
    scenes = []
    block_number = 1

    pov = context.main_pov_character or names[0]

    for scene_index, chunk in enumerate(scene_chunks, start=1):
        scene_id = f"S{scene_index:03d}"
        scene_text = "\n\n".join(chunk)
        blocks = []

        for block_text in split_blocks(scene_text):
            block_id = f"B{block_number:04d}"
            mentioned = [n for n in names if re.search(rf"\b{re.escape(n)}\b", block_text)]
            character = mentioned[0] if mentioned else pov
            for m in mentioned or [character]:
                if scene_id not in character_scene_map[m]:
                    character_scene_map[m].append(scene_id)

            locations = detect_terms(block_text, LOCATION_WORDS, context.known_locations)
            equipment = detect_terms(block_text, EQUIPMENT_WORDS, context.known_equipment)
            sfx = detect_sfx(block_text)
            emotion = detect_emotion(block_text)
            duration = estimate_duration(block_text)

            blocks.append(ProductionBlock(
                id=block_id,
                scene_id=scene_id,
                text=block_text,
                character=character,
                duration_seconds=duration,
                voice={
                    "emotion": emotion,
                    "pace": "slow immersive" if emotion != "battle tension" else "tense controlled",
                    "pause_after": 0.7,
                    "delivery": context.voice_style or "restrained first-person narration",
                },
                image_prompt=image_prompt(block_text, context, locations, equipment, character, emotion),
                music_cue=music_cue(emotion, sfx),
                locations=locations,
                equipment=equipment,
                sfx=sfx,
                ambience=locations or ["subtle historical room tone"],
            ))
            block_number += 1

        scenes.append(ProductionScene(
            id=scene_id,
            title=first_clean_sentence(scene_text, 54),
            summary=first_clean_sentence(scene_text, 240),
            blocks=blocks,
            locations=sorted(set(x for b in blocks for x in b.locations)),
            equipment=sorted(set(x for b in blocks for x in b.equipment)),
        ))

    characters = []
    for name in names:
        scenes_for_char = character_scene_map.get(name, [])
        characters.append(CharacterProfile(
            id=name.upper().replace(" ", "_"),
            name=name,
            role="POV narrator" if name == pov else "supporting character",
            baseline=f"Detected automatically. Appears in {len(scenes_for_char)} scene(s).",
            appears_in_scenes=scenes_for_char,
        ))

    total_chars = sum(len(b.text) for s in scenes for b in s.blocks)

    plan = ProductionPlan(
        title=context.project_title,
        source="final_generic_deterministic_analyzer",
        context=context,
        characters=characters,
        scenes=scenes,
        style_bible={
            "visual_style": "cinematic historical realism, immersive first-person POV, grounded sensory detail",
            "camera": "eye-level human perspective, documentary still, no poster posing",
            "lighting": "natural practical light based on script",
            "negative_prompt": "fantasy, modern objects, modern roads, text, watermark, video game style",
        },
        production_policy={
            "paid_ai_allowed": "voice_only",
            "script_analysis": "local/free",
            "images": "local/free or placeholders",
            "music": "local/imported only",
        },
    ).to_dict()

    plan["estimated_runtime_seconds"] = sum(b["duration_seconds"] for s in plan["scenes"] for b in s["blocks"])
    plan["estimated_voice_cost"] = total_chars * 0.000015
    return plan
''', encoding="utf-8")


(PKG / "validators.py").write_text(r'''
from __future__ import annotations


def validate_plan(plan: dict) -> tuple[bool, list[str]]:
    errors = []

    if not isinstance(plan, dict):
        return False, ["Plan is not a dictionary."]

    if not plan.get("title"):
        errors.append("Missing title.")

    if not plan.get("scenes"):
        errors.append("No scenes detected.")

    for s in plan.get("scenes", []):
        if not s.get("id"):
            errors.append("Scene missing id.")
        if not s.get("blocks"):
            errors.append(f"Scene {s.get('id', '?')} has no blocks.")
        for b in s.get("blocks", []):
            if not b.get("text"):
                errors.append(f"Block {b.get('id', '?')} has no text.")
            if not b.get("image_prompt"):
                errors.append(f"Block {b.get('id', '?')} missing image prompt.")
            if not b.get("music_cue"):
                errors.append(f"Block {b.get('id', '?')} missing music cue.")

    return len(errors) == 0, errors
''', encoding="utf-8")


(PKG / "analyzer.py").write_text(r'''
from __future__ import annotations

from .models import AnalysisContext
from .deterministic import analyze_deterministic
from .validators import validate_plan


class GenericScriptAnalyzer:
    """
    Final-ready generic analyzer facade.

    It is intentionally script-agnostic:
    no Roman/Cannae/Viking/WW1 hardcoding.
    Specific context is passed through AnalysisContext.
    """

    def analyze(self, script: str, context: AnalysisContext) -> dict:
        plan = analyze_deterministic(script, context)
        ok, errors = validate_plan(plan)
        plan["validation"] = {"ok": ok, "errors": errors}
        return plan


def plan_metrics(plan: dict) -> dict:
    scenes = plan.get("scenes", [])
    blocks = [b for s in scenes for b in s.get("blocks", [])]
    locations = set(x for b in blocks for x in b.get("locations", []))
    equipment = set(x for b in blocks for x in b.get("equipment", []))
    sfx = set(x for b in blocks for x in b.get("sfx", []))

    return {
        "scenes": len(scenes),
        "blocks": len(blocks),
        "characters": len(plan.get("characters", [])),
        "locations": len(locations),
        "equipment": len(equipment),
        "sfx": len(sfx),
        "ambience": len(set(x for b in blocks for x in b.get("ambience", []))),
        "images": len(blocks),
        "music_cues": len(blocks),
        "words": sum(len((b.get("text") or "").split()) for b in blocks),
        "runtime_minutes": (plan.get("estimated_runtime_seconds", 0) or 0) / 60,
        "voice_cost": plan.get("estimated_voice_cost", 0.0) or 0.0,
    }


def plan_to_legacy_importer_shape(plan: dict) -> dict:
    return {
        "title": plan.get("title", "Historical POV Project"),
        "source": plan.get("source", "generic_analysis"),
        "characters": plan.get("characters", []),
        "scenes": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "summary": s.get("summary", ""),
                "blocks": [
                    {
                        "id": b.get("id"),
                        "text": b.get("text", ""),
                        "scene_label": b.get("id", ""),
                        "duration_seconds": b.get("duration_seconds", 10),
                        "characters": [b.get("character", "Narrator")],
                        "locations": b.get("locations", []),
                        "equipment": b.get("equipment", []),
                        "voice": b.get("voice", {}),
                        "image_prompt": b.get("image_prompt", ""),
                        "music_cue": b.get("music_cue", ""),
                        "sfx": b.get("sfx", []),
                        "ambience": b.get("ambience", []),
                    }
                    for b in s.get("blocks", [])
                ],
            }
            for s in plan.get("scenes", [])
        ],
        "style_bible": plan.get("style_bible", {}),
        "production_policy": plan.get("production_policy", {}),
    }
''', encoding="utf-8")


wizard = ROOT / "hps_qt" / "dialogs" / "project_wizard.py"
w = wizard.read_text(encoding="utf-8")

# imports
w = w.replace(
    "from hps.core.v25_production_analyzer import build_production_plan, plan_metrics, plan_to_legacy_importer_shape\n",
    ""
)
w = w.replace(
    "from hps.core.v25_analyzer import plan_metrics\n",
    ""
)

if "from hps.core.analysis.models import AnalysisContext\n" not in w:
    w = w.replace(
        "from hps.core.script_importer import ScriptImporter\n",
        "from hps.core.script_importer import ScriptImporter\n"
        "from hps.core.analysis.models import AnalysisContext\n"
        "from hps.core.analysis.analyzer import GenericScriptAnalyzer, plan_metrics, plan_to_legacy_importer_shape\n"
    )

# replace _plan_stats
start = w.find("def _plan_stats(plan: dict) -> dict:")
end = w.find("\n\n\nclass ProjectWizardDialog", start)
if start != -1 and end != -1:
    w = w[:start] + '''def _plan_stats(plan: dict) -> dict:
    stats = plan_metrics(plan)
    stats.setdefault("voice_cost", 0.0)
    stats.setdefault("images", 0)
    stats.setdefault("music_cues", 0)
    stats.setdefault("locations", 0)
    stats.setdefault("equipment", 0)
    stats.setdefault("sfx", 0)
    stats.setdefault("ambience", 0)
    return stats
''' + w[end:]

# replace analyze_script
start = w.find("    def analyze_script(self):")
end = w.find("    def populate_preview(self, plan: dict):", start)
if start != -1 and end != -1:
    w = w[:start] + r'''    def analyze_script(self):
        script = self.script_text.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Empty script", "Paste or import a script first.")
            return

        title = self.project_title.text().strip() or "Historical POV Project"

        self.summary.setPlainText(
            "Analyzing script with final generic analyzer...\n\n"
            "This analyzer is story-agnostic and does not contain Cannae-specific rules."
        )
        self.generate_btn.setEnabled(False)

        try:
            context = AnalysisContext(
                project_title=title,
                historical_period=self.period.text().strip(),
                voice_style=self.voice_style.text().strip(),
                target_runtime_minutes=int(self.target_runtime.text().strip() or "75"),
            )
            analyzer = GenericScriptAnalyzer()
            plan = analyzer.analyze(script, context)
        except Exception as exc:
            QMessageBox.warning(self, "Analysis failed", str(exc))
            return

        self.plan = plan
        self.populate_preview(plan)
        self.generate_btn.setEnabled(True)

''' + w[end:]

# make summary include validation if possible
w = w.replace(
    "Ollama note:\\n{ollama_error if ollama_error else 'No error.'}",
    "Validation:\\n{plan.get('validation', {}).get('errors', ['OK'])}"
)

wizard.write_text(w, encoding="utf-8")

# Keep old prototypes but document final architecture
(ROOT / "docs" / "V25_FINAL_ANALYSIS_ARCHITECTURE.md").write_text("""# V25 Final Analysis Architecture

Final-ready generic analysis system.

Modules:

- hps/core/analysis/models.py
- hps/core/analysis/preprocessor.py
- hps/core/analysis/deterministic.py
- hps/core/analysis/validators.py
- hps/core/analysis/analyzer.py

Rules:

- No script-specific hardcoding.
- No Cannae-specific character list.
- No paid AI in analysis.
- Voice remains the only paid/API step.
- Analyzer receives optional context from the wizard.
- Empty context still works by discovery.

The old prototype analyzers remain in the repo temporarily but the wizard now uses:

GenericScriptAnalyzer
""", encoding="utf-8")

print("Final generic analysis architecture installed.")
print("Run: .\\run_studio_v24.bat")