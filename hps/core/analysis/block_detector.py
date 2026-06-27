
from __future__ import annotations
import re
from .preprocessor import word_count, first_clean_sentence


def split_blocks(scene_text: str, target_words: int = 130) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", scene_text.strip())
    blocks, cur, n = [], [], 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        wc = word_count(s)
        if cur and n + wc > target_words:
            blocks.append(" ".join(cur).strip())
            cur, n = [], 0
        cur.append(s)
        n += wc

    if cur:
        blocks.append(" ".join(cur).strip())

    return [b for b in blocks if b]


def title_block(text: str, block_id: str) -> str:
    t = first_clean_sentence(text, 46)
    junk = [
        "THE FLIES ALWAYS FOUND US FIRST",
        "The Battle of Cannae — A First Person Narration",
        "Production Script — 60–70 minutes",
    ]
    for j in junk:
        t = t.replace(j, "")
    t = t.strip(" -*#")
    return t or block_id
