"""Section-aware chunking.

Chunks are about ``max_tokens`` long with a fractional ``overlap``, split on paragraph and then
sentence boundaries, and never cross a section heading. Token counts use a fast word-piece
approximation (≈1.3 tokens per word for English scientific text), which is accurate enough for
sizing and avoids loading a tokenizer during indexing.
"""

from __future__ import annotations

import re

from georag.schemas import Chunk, Document

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
_WORD = re.compile(r"\S+")


def approx_tokens(text: str) -> int:
    return int(len(_WORD.findall(text)) * 1.3) + 1


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # Protect common abbreviations so they do not end a sentence.
    protected = re.sub(
        r"\b(e\.g|i\.e|et al|Fig|Eq|vs|approx|ca|cf)\.", lambda m: m.group(0).replace(".", "§"), text
    )
    return [s.replace("§", ".").strip() for s in _SENT_SPLIT.split(protected) if s.strip()]


def _pack(units: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for unit in units:
        n = approx_tokens(unit)
        if current and size + n > max_tokens:
            chunks.append(" ".join(current))
            # Carry the tail of the previous chunk forward as overlap.
            tail: list[str] = []
            tail_size = 0
            for prev in reversed(current):
                t = approx_tokens(prev)
                if tail_size + t > overlap_tokens:
                    break
                tail.insert(0, prev)
                tail_size += t
            current, size = tail, tail_size
        current.append(unit)
        size += n
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_text(text: str, max_tokens: int = 500, overlap: float = 0.15) -> list[str]:
    if approx_tokens(text) <= max_tokens:
        return [re.sub(r"\s+", " ", text).strip()]
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if approx_tokens(para) <= max_tokens:
            units.append(re.sub(r"\s+", " ", para))
        else:
            units.extend(split_sentences(para))
    # A single sentence longer than the budget is split on words as a last resort.
    final_units: list[str] = []
    for u in units:
        if approx_tokens(u) <= max_tokens:
            final_units.append(u)
        else:
            words = u.split()
            step = int(max_tokens / 1.3)
            final_units.extend(" ".join(words[i : i + step]) for i in range(0, len(words), step))
    return _pack(final_units, max_tokens, int(max_tokens * overlap))


def chunk_document(doc: Document, max_tokens: int = 500, overlap: float = 0.15) -> list[Chunk]:
    sections = doc.sections or [("Abstract" if doc.source in ("arxiv", "openalex") else "", doc.text)]
    chunks: list[Chunk] = []
    for heading, body in sections:
        for piece in chunk_text(body, max_tokens, overlap):
            if len(piece) < 40:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{len(chunks)}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    section=heading,
                    text=piece,
                    domain=doc.domain,
                    year=doc.year,
                    url=doc.url,
                )
            )
    return chunks
