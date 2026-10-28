"""Indexing pipeline: corpus → chunks → BM25 → dense vectors → knowledge graph.

Every stage is idempotent (fingerprinted inputs, ``.done`` markers) and logs its wall time to
``results/compute_log.jsonl``. Models are loaded one stage at a time so the whole pipeline fits
on a single consumer GPU, or on a CPU.
"""

from __future__ import annotations

import gc
import json
import logging
from pathlib import Path

import httpx

from georag.config import Settings
from georag.corpus import arxiv, catalogue, docs
from georag.corpus.build import (
    corpus_stats,
    glossary_documents,
    read_documents,
    save_stats,
    write_documents,
    write_manifest,
)
from georag.index.chunking import chunk_document
from georag.index.dense import DenseIndex, HashingEmbedder, SentenceTransformerEmbedder
from georag.index.graph import KnowledgeGraph, load_glossary
from georag.index.sparse import BM25Index
from georag.index.store import Stage, fingerprint, load_chunks, save_chunks

log = logging.getLogger("georag.pipeline")


def download_snapshot(raw_dir: Path) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with httpx.Client(timeout=600, follow_redirects=True) as client:
        for url in arxiv.snapshot_urls():
            dest = raw_dir / url.rsplit("/", 1)[-1]
            if not dest.exists():
                log.info("downloading %s", dest.name)
                tmp = dest.with_suffix(".part")
                with client.stream("GET", url) as r, tmp.open("wb") as f:
                    r.raise_for_status()
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
            paths.append(dest)
    return paths


def build_corpus(s: Settings, source: str = "arxiv", force: bool = False) -> dict:
    p = s.paths.ensure()
    domains_cfg = p.root / "configs" / "domains.yaml"
    stage = Stage("corpus", p.corpus, p.results / "compute_log.jsonl")
    fp = fingerprint(domains_cfg, p.glossary, source)

    def run() -> dict:
        rules, cfg = arxiv.load_domain_rules(domains_cfg)
        years, per_domain = tuple(cfg["years"]), cfg["per_domain"]
        if source == "openalex":
            from georag.corpus import openalex

            papers = openalex.collect(rules, years, per_domain, p.raw / "pdf")
        else:
            shards = sorted(p.raw.glob("train-*.parquet")) or download_snapshot(p.raw)
            papers = arxiv.select_papers(shards, rules, years, per_domain)
        tech = docs.fetch_docs()
        cat, cat_source = catalogue.fetch_catalogue()
        gloss = glossary_documents(p.glossary)
        all_docs = papers + tech + cat + gloss
        write_documents(all_docs, p.corpus / "documents.jsonl")
        df = write_manifest(all_docs, p.manifest)
        stats = corpus_stats(df)
        stats["catalogue_source"] = cat_source
        save_stats(stats, p.results / "corpus_stats.json")
        return {"documents": len(all_docs), "papers": len(papers), "docs": len(tech), "catalogue": len(cat)}

    return stage.run(fp, run, force)


def build_index(s: Settings, light: bool = False, force: bool = False) -> dict:
    p = s.paths.ensure()
    r = s.retrieval
    docs_path = p.corpus / "documents.jsonl"
    log_path = p.results / "compute_log.jsonl"
    out: dict = {}

    # ---- chunks
    chunk_stage = Stage("chunk", p.index / "chunks", log_path)
    fp_chunks = fingerprint(docs_path, str(r.chunk_tokens), str(r.chunk_overlap))

    def do_chunks() -> dict:
        documents = read_documents(docs_path)
        chunks = [c for d in documents for c in chunk_document(d, r.chunk_tokens, r.chunk_overlap)]
        save_chunks(chunks, p.index / "chunks.parquet")
        return {"chunks": len(chunks)}

    out["chunk"] = chunk_stage.run(fp_chunks, do_chunks, force)
    chunks = load_chunks(p.index / "chunks.parquet")
    ids = [c.chunk_id for c in chunks]
    texts = [c.indexed_text for c in chunks]

    # ---- BM25
    def do_bm25() -> dict:
        BM25Index.build(ids, texts).save(p.index / "bm25")
        return {"chunks": len(ids)}

    out["bm25"] = Stage("bm25", p.index / "bm25", log_path).run(fp_chunks, do_bm25, force)

    # ---- dense
    model_name = "hashing-256" if light else r.embedding_model

    def do_dense() -> dict:
        emb = (
            HashingEmbedder(256)
            if light
            else SentenceTransformerEmbedder(r.embedding_model, r.device, p.models)
        )
        vecs = emb.embed_documents(texts, batch_size=16)
        DenseIndex(vecs, ids, model_name).save(p.index / "dense")
        del emb
        gc.collect()
        return {"chunks": len(ids), "dim": int(vecs.shape[1]), "model": model_name}

    out["dense"] = Stage("dense", p.index / "dense", log_path).run(
        fingerprint(fp_chunks, model_name), do_dense, force
    )

    # ---- graph
    def do_graph() -> dict:
        g = KnowledgeGraph.build(chunks, load_glossary(p.glossary))
        g.save(p.index / "graph")
        stats = g.stats()
        (p.results / "graph_stats.json").write_text(json.dumps(stats, indent=2))
        return stats

    out["graph"] = Stage("graph", p.index / "graph", log_path).run(
        fingerprint(fp_chunks, p.glossary), do_graph, force
    )
    return out
