
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
