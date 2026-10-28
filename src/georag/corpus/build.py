"""Assemble the corpus and write the licence register (``corpus/manifest.parquet``).

The manifest is the only corpus artefact that is committed: it lists every document with its
identifier, licence, URL and a SHA-256 of the indexed text, so anyone can rebuild and verify the
same corpus. Documents themselves live in ``data/corpus/documents.jsonl`` (git-ignored).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from georag.schemas import Document


def glossary_documents(path: Path) -> list[Document]:
    terms = yaml.safe_load(path.read_text())
    docs = []
    for t in terms:
        aliases = ", ".join(a for a in t["aliases"] if a != t["label"])
        text = f"{t['label']} ({t['type']}). {t['definition']}"
        if aliases:
            text += f" Also known as: {aliases}."
        docs.append(
            Document(
                doc_id=f"glossary:{t['id']}",
                source="glossary",
                title=f"Glossary: {t['label']}",
                text=text,
                domain="glossary",
                licence="CC-BY-4.0",
                authors=["GeoRAG glossary"],
                url=f"https://github.com/emna-saada/GeoRAG/blob/main/corpus/glossary.yaml#{t['id']}",
            )
        )
    return docs


def write_documents(docs: list[Document], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for d in docs:
            f.write(d.model_dump_json() + "\n")


def read_documents(path: Path) -> list[Document]:
    with path.open() as f:
        return [Document.model_validate_json(line) for line in f if line.strip()]


def write_manifest(docs: list[Document], path: Path) -> pd.DataFrame:
    rows = []
    for d in docs:
        rows.append(
            {
                "doc_id": d.doc_id,
                "source": d.source,
                "domain": d.domain,
                "title": d.title,
                "authors": "; ".join(d.authors),
                "year": d.year,
                "doi": d.doi,
                "url": d.url,
                "licence": d.licence,
                "sha256": hashlib.sha256(d.text.encode()).hexdigest(),
                "chars": len(d.text),
            }
        )
    df = pd.DataFrame(rows)
    df["year"] = df["year"].astype("Int64")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def corpus_stats(df: pd.DataFrame) -> dict:
    return {
        "documents": len(df),
        "by_source": df["source"].value_counts().to_dict(),
        "by_domain": df["domain"].value_counts().to_dict(),
        "papers_by_year": {
            int(k): int(v)
            for k, v in df[df.source.isin(["arxiv", "openalex"])]["year"].value_counts().sort_index().items()
        },
        "open_licence_papers": int(
            df[df.source.isin(["arxiv", "openalex"])]["licence"]
            .fillna("")
            .str.contains("creativecommons|cc-by|cc0")
            .sum()
        ),
    }


def save_stats(stats: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2))
