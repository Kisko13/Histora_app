from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "hps" / "core" / "analysis"

# ------------------------------------------------------------
# speaker_tags.py
# ------------------------------------------------------------

(PKG / "speaker_tags.py").write_text(r'''
from __future__ import annotations

import re
from dataclasses import dataclass


TAG_RE = re.compile(r"^\s*\[([A-Za-z0-9 _.'-]+)(?:\|([^\]]+))?\]\s*$")


@dataclass
class TaggedBlock:
    speaker: str
    text: str
    directives: list[str]


def parse_speaker_tag(line: str):
    m = TAG_RE.match(line or "")
    if not m:
        return None

    speaker = " ".join(m.group(1).strip().split())
    directives_raw = m.group(2) or ""
    directives = [x.strip() for x in directives_raw.split("|") if x.strip()]
    return speaker, directives


def has_speaker_tags(script: str) -> bool:
    return any(parse_speaker_tag(line) for line in (script or "").splitlines())


def parse_tagged_script(script: str, default_speaker: str = "Narrator") -> list[TaggedBlock]:
    """
    Converts:

    [Marcus]
    spoken text

    [Titus | whisper | slow]
    spoken text

    into clean blocks where speaker is metadata and text contains no tags.
    """
    blocks: list[TaggedBlock] = []
    current_speaker = default_speaker
    current_directives: list[str] = []
    buffer: list[str] = []

    def flush():
        nonlocal buffer
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(TaggedBlock(
                speaker=current_speaker,
                text=text,
                directives=list(current_directives),
            ))
        buffer = []

    for line in (script or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        parsed = parse_speaker_tag(line)
        if parsed:
            flush()
            current_speaker, current_directives = parsed
            continue
        buffer.append(line)

    flush()
    return blocks


def clean_script_without_tags(script: str) -> str:
    lines = []
    for line in (script or "").splitlines():
        if parse_speaker_tag(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()
''', encoding="utf-8")


# ------------------------------------------------------------
# Patch character_detector.py
# ------------------------------------------------------------

char_file = PKG / "character_detector.py"
c = char_file.read_text(encoding="utf-8")

if "from .speaker_tags import has_speaker_tags, parse_tagged_script" not in c:
    c = c.replace(
        "from collections import Counter\n",
        "from collections import Counter\nfrom .speaker_tags import has_speaker_tags, parse_tagged_script\n"
    )

old = '''def detect_characters(script: str, known: list[str] | None = None, main_pov: str = "") -> list[dict]:
    known = [normalize_name(x) for x in (known or []) if normalize_name(x)]
    main_pov = normalize_name(main_pov)

    if known or main_pov:'''

new = '''def detect_characters(script: str, known: list[str] | None = None, main_pov: str = "") -> list[dict]:
    known = [normalize_name(x) for x in (known or []) if normalize_name(x)]
    main_pov = normalize_name(main_pov)

    if has_speaker_tags(script):
        speakers = []
        for block in parse_tagged_script(script, main_pov or "Narrator"):
            n = normalize_name(block.speaker)
            if n and n not in speakers:
                speakers.append(n)

        return [
            {
                "id": n.upper().replace(" ", "_"),
                "name": n,
                "role": "POV narrator" if n == main_pov else ("narrator" if n.lower() == "narrator" else "script speaker"),
                "baseline": "Detected from [Speaker] production tag. Tag is metadata and is not sent to voice generation.",
                "appears_in_scenes": [],
            }
            for n in speakers
        ]

    if known or main_pov:'''

if old not in c:
    raise RuntimeError("Could not patch detect_characters start.")
c = c.replace(old, new)

char_file.write_text(c, encoding="utf-8")


# ------------------------------------------------------------
# Patch scene_detector.py to ignore tags as headings/text noise
# ------------------------------------------------------------

scene_file = PKG / "scene_detector.py"
s = scene_file.read_text(encoding="utf-8")

if "from .speaker_tags import parse_speaker_tag" not in s:
    s = s.replace(
        "from .preprocessor import split_paragraphs, word_count, first_clean_sentence\n",
        "from .preprocessor import split_paragraphs, word_count, first_clean_sentence\nfrom .speaker_tags import parse_speaker_tag\n"
    )

s = s.replace(
'''    stripped = p.strip()
    wc = word_count(stripped)''',
'''    stripped = p.strip()
    if parse_speaker_tag(stripped):
        return True
    wc = word_count(stripped)'''
)

scene_file.write_text(s, encoding="utf-8")


# ------------------------------------------------------------
# Patch analyzer.py to use tagged blocks directly when present
# ------------------------------------------------------------

analyzer = PKG / "analyzer.py"
a = analyzer.read_text(encoding="utf-8")

if "from .speaker_tags import has_speaker_tags, parse_tagged_script" not in a:
    a = a.replace(
        "from .validators import validate_plan\n",
        "from .validators import validate_plan\nfrom .speaker_tags import has_speaker_tags, parse_tagged_script\n"
    )

old_analyze_head = '''    def analyze(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        dialogue_mode = detect_dialogue_mode(script)

        raw_scenes = split_scenes(script)
        scenes = []
        block_counter = 1'''

new_analyze_head = '''    def analyze(self, script: str, context: AnalysisContext) -> dict:
        characters = detect_characters(script, context.known_characters, context.main_pov_character)
        dialogue_mode = detect_dialogue_mode(script)
        tagged_mode = has_speaker_tags(script)

        raw_scenes = split_scenes(script)
        scenes = []
        block_counter = 1'''

if old_analyze_head not in a:
    raise RuntimeError("Could not patch analyzer analyze header.")
a = a.replace(old_analyze_head, new_analyze_head)

old_loop = '''            for block_text in split_blocks(scene_text):
                bid = f"B{block_counter:04d}"
                character = assign_character(block_text, characters, block_counter, dialogue_mode)'''

new_loop = '''            if tagged_mode:
                tagged_blocks = parse_tagged_script(scene_text, context.main_pov_character or "Narrator")
                block_texts = [(tb.text, tb.speaker, tb.directives) for tb in tagged_blocks]
            else:
                block_texts = [(txt, None, []) for txt in split_blocks(scene_text)]

            for block_text, tagged_speaker, tag_directives in block_texts:
                bid = f"B{block_counter:04d}"
                character = tagged_speaker or assign_character(block_text, characters, block_counter, dialogue_mode)'''

if old_loop not in a:
    raise RuntimeError("Could not patch analyzer block loop.")
a = a.replace(old_loop, new_loop)

# add tag metadata inside block dict
a = a.replace(
'''"production_notes": production_notes(character, locations, equipment),
                })''',
'''"production_notes": {
                        **production_notes(character, locations, equipment),
                        "speaker_tag_source": bool(tagged_speaker),
                        "speaker_tag_directives": tag_directives,
                        "voice_text_clean": True,
                    },
                })'''
)

analyzer.write_text(a, encoding="utf-8")


# ------------------------------------------------------------
# Patch plan_to_legacy_importer_shape so clean text is sent forward
# ------------------------------------------------------------
# Already uses b["text"], which is clean in tagged mode. Add metadata pass-through.
a = analyzer.read_text(encoding="utf-8")
a = a.replace(
'''"ambience": b.get("ambience", []),
                    }''',
'''"ambience": b.get("ambience", []),
                        "production_notes": b.get("production_notes", {}),
                    }'''
)
analyzer.write_text(a, encoding="utf-8")


# ------------------------------------------------------------
# Docs
# ------------------------------------------------------------

(ROOT / "docs" / "V26_SPEAKER_TAG_SUPPORT.md").write_text("""# V26 Speaker Tag Support

Adds production speaker tags:

```text
[Marcus]
The flies always found us before dawn.

[Titus]
Keep your shield close.