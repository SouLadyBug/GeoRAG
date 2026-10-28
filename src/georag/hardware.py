"""Detect the GPU and pick a model tier.

The tier decides which generator is pulled into Ollama and which embedding model is used.
``georag hardware`` writes the result to ``configs/hardware.yaml``; nothing else needs to be
chosen by hand.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Tier:
    name: str
    min_vram_gb: float
    generator: str
    fallbacks: tuple[str, ...]
    vision: str | None
    embedding: str
    reranker: str
    corpus_target: int


TIERS: tuple[Tier, ...] = (
    Tier(
        name="cpu",
        min_vram_gb=0,
        generator="qwen3:4b",
        fallbacks=("qwen3:1.7b",),
        vision=None,
        embedding="Qwen/Qwen3-Embedding-0.6B",
        reranker="Qwen/Qwen3-Reranker-0.6B",
        corpus_target=2000,
    ),
    Tier(
        name="8gb",
        min_vram_gb=7.5,
        generator="qwen3:8b",
        fallbacks=("qwen3:4b",),
        vision="qwen2.5vl:7b",
        embedding="Qwen/Qwen3-Embedding-0.6B",
        reranker="Qwen/Qwen3-Reranker-0.6B",
        corpus_target=1000,
    ),
    Tier(
        name="16gb",
        min_vram_gb=11.5,
        generator="gpt-oss:20b",
        fallbacks=("qwen3.5:9b", "qwen3:14b"),
        vision="qwen3.5:9b",
        embedding="Qwen/Qwen3-Embedding-4B",
        reranker="Qwen/Qwen3-Reranker-0.6B",
        corpus_target=2000,
    ),
    Tier(
        name="24gb",
        min_vram_gb=23.0,
        generator="qwen3.8:27b",
        fallbacks=("qwen3:32b", "gpt-oss:20b"),
        vision="qwen3.8:27b",
        embedding="Qwen/Qwen3-Embedding-4B",
        reranker="Qwen/Qwen3-Reranker-0.6B",
        corpus_target=2500,
    ),
)


@dataclass
class GPUInfo:
    name: str
    vram_gb: float
    driver: str


def detect_gpus() -> list[GPUInfo]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    gpus = []
    for line in out.strip().splitlines():
        name, mem, driver = (part.strip() for part in line.split(","))
        gpus.append(GPUInfo(name=name, vram_gb=round(float(mem) / 1024, 1), driver=driver))
    return gpus


def choose_tier(vram_gb: float) -> Tier:
    chosen = TIERS[0]
    for tier in TIERS:
        if vram_gb >= tier.min_vram_gb:
            chosen = tier
    return chosen


def write_hardware_config(path: Path) -> dict:
    gpus = detect_gpus()
    vram = max((g.vram_gb for g in gpus), default=0.0)
    tier = choose_tier(vram)
    config: dict = {
        "tier": tier.name,
        "detected": {
            "gpus": [asdict(g) for g in gpus],
            "cpu": platform.processor() or platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "llm": {"model": tier.generator, "fallbacks": list(tier.fallbacks), "vision": tier.vision},
        "retrieval": {
            "embedding_model": tier.embedding,
            "reranker_model": tier.reranker,
            "device": "cuda" if gpus else "cpu",
            # Cross-encoder reranking dominates CPU latency; 20 candidates keep a query under a minute.
            "rerank_top_k": 30 if gpus else 20,
        },
        "corpus_target": tier.corpus_target,
    }
    # LLMSettings does not know about these keys; keep them in a side section.
    llm_extra = {"fallbacks": config["llm"].pop("fallbacks"), "vision": config["llm"].pop("vision")}
    config["models"] = llm_extra
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return config
