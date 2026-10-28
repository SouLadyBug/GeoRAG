"""Optional: open-access full text from OpenAlex.

Requires a free API key (``OPENALEX_API_KEY`` in ``.env``) and the ``openalex`` + ``pdf`` extras.
Only works with a CC BY or CC0 primary-location licence are kept, and PDFs are downloaded from
``best_oa_location.pdf_url`` at no more than one request per second with a contact address in
the User-Agent. Failures are skipped, never retried aggressively.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from georag.corpus.arxiv import DomainRule
from georag.schemas import Document

LICENCE_FILTER = "cc-by|cc0"


def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    if not inverted:
        return ""
    positions = [(pos, word) for word, poss in inverted.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))


def iter_works(rule: DomainRule, years: tuple[int, int], limit: int) -> Iterator[dict]:
    from pyalex import Works, config  # optional dependency

    config.api_key = os.environ.get("OPENALEX_API_KEY")
    config.email = os.environ.get("CONTACT_EMAIL")
    query = (
        Works()
        .search(rule.openalex_search)
        .filter(
            is_oa=True,
            primary_location={"license": LICENCE_FILTER},
            publication_year=f"{years[0]}-{years[1]}",
            has_abstract=True,
        )
        .sort(relevance_score="desc")
    )
    n = 0
    for page in query.paginate(per_page=100, n_max=limit * 3):
        for work in page:
            yield work
            n += 1
            if n >= limit * 3:
                return


def download_pdf(client: httpx.Client, url: str, dest: Path, min_interval: float = 1.0) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    time.sleep(min_interval)
    try:
        resp = client.get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        return None
    dest.write_bytes(resp.content)
    return dest


def parse_pdf(path: Path) -> list[tuple[str, str, int]]:
    """Return (section heading, text, page) triples using pymupdf4llm's markdown output."""
    import pymupdf4llm  # optional dependency

    out: list[tuple[str, str, int]] = []
    pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    heading = "Body"
    for page in pages:
        page_no = page["metadata"].get("page", 0)
        buf: list[str] = []
        for line in page["text"].splitlines():
            if line.startswith("#"):
                if buf:
                    out.append((heading, "\n".join(buf), page_no))
                    buf = []
                heading = line.lstrip("#").strip().strip("*") or heading
            else:
                buf.append(line)
        if buf:
            out.append((heading, "\n".join(buf), page_no))
    return out


def collect(
    rules: dict[str, DomainRule], years: tuple[int, int], per_domain: int, pdf_dir: Path
) -> list[Document]:
    email = os.environ.get("CONTACT_EMAIL", "")
    headers = {"User-Agent": f"georag/0.1 (mailto:{email})"}
    docs: list[Document] = []
    seen: set[str] = set()
    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        for name, rule in rules.items():
            kept = 0
            for w in iter_works(rule, years, per_domain):
                if kept >= per_domain or w["id"] in seen:
                    continue
                seen.add(w["id"])
                lic = ((w.get("primary_location") or {}).get("license") or "").lower()
                if not (lic.startswith("cc-by") or lic == "cc0"):
                    continue
                pdf_url = (w.get("best_oa_location") or {}).get("pdf_url")
                sections = None
                if pdf_url:
                    pdf = download_pdf(
                        client, pdf_url, pdf_dir / f"{hashlib.sha1(w['id'].encode()).hexdigest()}.pdf"
                    )
                    if pdf:
                        try:
                            sections = [(h, t) for h, t, _ in parse_pdf(pdf)]
                        except Exception:  # broken PDFs are common; fall back to the abstract
                            sections = None
                abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
                docs.append(
                    Document(
                        doc_id=f"openalex:{w['id'].rsplit('/', 1)[-1]}",
                        source="openalex",
                        title=w.get("display_name") or "",
                        text=abstract,
                        domain=name,
                        year=w.get("publication_year"),
                        authors=[a["author"]["display_name"] for a in w.get("authorships", [])[:12]],
                        doi=(w.get("doi") or "").replace("https://doi.org/", "") or None,
                        url=w.get("doi") or w["id"],
                        licence=lic,
                        sections=sections,
                    )
                )
                kept += 1
    return docs
