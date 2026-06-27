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