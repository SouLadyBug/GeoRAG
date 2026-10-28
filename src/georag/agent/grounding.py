"""Citation parsing and the sentence-level support check shared by Ask, Design and Explore."""

from __future__ import annotations

import re

from georag.index.chunking import split_sentences
from georag.index.rerank import SUPPORT_INSTRUCTION, Scorer
from georag.schemas import Citation, Passage, Sentence

_CITE = re.compile(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]")


def format_sources(passages: list[Passage], numbers: list[int] | None = None, max_chars: int = 1100) -> str:
    numbers = numbers or list(range(1, len(passages) + 1))
    blocks = []
    for n, p in zip(numbers, passages, strict=True):
        c = p.chunk
        year = f" ({c.year})" if c.year else ""
        section = f" — {c.section}" if c.section and c.section not in ("Abstract", c.title) else ""
        text = c.text if len(c.text) <= max_chars else c.text[:max_chars].rsplit(" ", 1)[0] + " …"
        blocks.append(f"[{n}] {c.title}{year}{section}\n{text}")
    return "\n\n".join(blocks)


def parse_citations(token: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"\s*[,;]\s*", token):
        if re.fullmatch(r"\d+\s*[–-]\s*\d+", part):
            a, b = (int(x) for x in re.split(r"\s*[–-]\s*", part))
            if 0 < b - a < 10:
                nums.extend(range(a, b + 1))
                continue
        if part.strip().isdigit():
            nums.append(int(part))
    return list(dict.fromkeys(nums))


def split_cited(text: str, valid: set[int]) -> list[Sentence]:
    """Split an answer into sentences and attach the citations each one carries.

    A trailing citation group that a model puts after the full stop (``... water. [2]``) belongs
    to the preceding sentence. Citation numbers outside ``valid`` are dropped.
    """
    text = re.sub(r"\[?INSUFFICIENT_EVIDENCE\]?\.?", "", text)
    text = re.sub(r"\.\s*(\[\d[^\]]*\])", r" \1.", text.strip())
    sentences = []
    for raw in split_sentences(text):
        cites = [n for m in _CITE.finditer(raw) for n in parse_citations(m.group(1)) if n in valid]
        clean = _CITE.sub("", raw)
        # A citation used as a noun ("as described in [2], ...") leaves a dangling word behind.
        clean = re.sub(r"\s+(?:in|by|from|see|of|to)\s*(?=[,.;:)])", "", clean)
        clean = re.sub(r"\(\s*[,;]?\s*\)", "", clean)
        clean = re.sub(r"\s+([.,;:])", r"\1", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        if clean:
            sentences.append(Sentence(text=clean, citations=list(dict.fromkeys(cites))))
    return sentences


_COVERAGE = re.compile(
    r"^(the|these)?\s*(provided |retrieved )?(sources?|passages?) (do|does) not (cover|address|specify|describe|mention|provide)",
    re.I,
)


def is_coverage_note(text: str) -> bool:
    return bool(_COVERAGE.search(text.strip()))


def check_support(
    sentences: list[Sentence],
    sources: dict[int, Passage],
    scorer: Scorer | None,
    threshold: float,
) -> float | None:
    """Score each sentence against its cited passages; return the supported fraction.

    Sentences without a citation are unsupported by definition. Without a scorer, only the
    presence of a valid citation is checked.
    """
    if not sentences:
        return None
    claims = 0
    for s in sentences:
        if is_coverage_note(s.text):
            # "The sources do not cover X" is a statement about the evidence, not a claim to check.
            s.support, s.supported = None, True
            continue
        claims += 1
        if not s.citations:
            s.support, s.supported = 0.0, False
            continue
        if scorer is None:
            s.support, s.supported = None, True
            continue
        docs = [sources[n].chunk.text for n in s.citations if n in sources]
        scores = scorer.score(s.text, docs, SUPPORT_INSTRUCTION) if docs else [0.0]
        s.support = round(max(scores), 4)
        s.supported = s.support >= threshold
    if not claims:
        return None
    return sum(s.supported for s in sentences if not is_coverage_note(s.text)) / claims


def render_cited(sentences: list[Sentence], mark_unsupported: bool = True) -> str:
    parts = []
    for s in sentences:
        cite = f" [{', '.join(map(str, s.citations))}]" if s.citations else ""
        body = s.text.rstrip(".?!")
        end = s.text[-1] if s.text[-1] in ".?!" else "."
        flag = " ⚠" if mark_unsupported and not s.supported else ""
        parts.append(f"{body}{cite}{end}{flag}")
    return " ".join(parts)


def make_citation(n: int, p: Passage) -> Citation:
    c = p.chunk
    quote = c.text if len(c.text) <= 320 else c.text[:320].rsplit(" ", 1)[0] + " …"
    return Citation(
        n=n,
        chunk_id=c.chunk_id,
        doc_id=c.doc_id,
        title=c.title,
        url=c.url,
        year=c.year,
        section=c.section,
        quote=quote,
    )
