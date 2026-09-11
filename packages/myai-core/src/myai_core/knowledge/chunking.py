"""Paragraph-aware chunking with overlap."""

from __future__ import annotations

import re

TARGET_CHARS = 900
MAX_CHARS = 1200
OVERLAP_CHARS = 120

_PARA_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str) -> list[str]:
    """Split text into chunks of roughly ``TARGET_CHARS``, never mid-word, with overlap."""
    normalised = text.replace("\r\n", "\n").strip()
    if not normalised:
        return []
    units: list[str] = []
    for para in _PARA_SPLIT.split(normalised):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= MAX_CHARS:
            units.append(para)
        else:
            units.extend(_split_long(para))

    chunks: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= TARGET_CHARS:
            current = f"{current}\n{unit}"
        else:
            chunks.append(current)
            tail = current[-OVERLAP_CHARS:]
            tail = tail[tail.find(" ") + 1 :] if " " in tail else tail
            # Overlap only when it keeps the chunk within MAX_CHARS.
            current = f"{tail}\n{unit}" if tail and len(tail) + 1 + len(unit) <= MAX_CHARS else unit
    if current:
        chunks.append(current)
    return chunks


def _split_long(para: str) -> list[str]:
    out: list[str] = []
    buf = ""
    for sentence in _SENTENCE_SPLIT.split(para):
        if len(buf) + len(sentence) + 1 <= MAX_CHARS:
            buf = f"{buf} {sentence}".strip()
        else:
            if buf:
                out.append(buf)
            while len(sentence) > MAX_CHARS:  # pathological: no sentence breaks
                cut = sentence.rfind(" ", 0, MAX_CHARS)
                cut = cut if cut > 0 else MAX_CHARS
                out.append(sentence[:cut])
                sentence = sentence[cut:].lstrip()
            buf = sentence
    if buf:
        out.append(buf)
    return out
