"""Project settings.

Settings are layered: built-in defaults < ``configs/default.yaml`` < ``configs/hardware.yaml``
< environment variables (``GEORAG_*``). Everything that touches the file system goes through
:class:`Paths` so tests can point the whole pipeline at a temporary directory.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


class Paths(BaseModel):
    root: Path = ROOT
    data: Path = ROOT / "data"

    @property
    def raw(self) -> Path:
        return self.data / "raw"

    @property
    def corpus(self) -> Path:
        return self.data / "corpus"

    @property
    def index(self) -> Path:
        return self.data / "index"

    @property
    def runs(self) -> Path:
        return self.data / "runs"

    @property
    def models(self) -> Path:
        return self.data / "models"

    @property
    def manifest(self) -> Path:
        return self.root / "corpus" / "manifest.parquet"

    @property
    def glossary(self) -> Path:
        return self.root / "corpus" / "glossary.yaml"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def bench(self) -> Path:
        return self.root / "eval" / "bench"

    def ensure(self) -> Paths:
        for p in (self.raw, self.corpus, self.index, self.runs, self.models):
            p.mkdir(parents=True, exist_ok=True)
        return self


class LLMSettings(BaseModel):
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3:8b"
    api_key: str = "local"
    temperature: float = 0.2
    max_tokens: int = 700
    timeout_s: float = 600.0
    # Qwen3 hybrid models think by default; '/no_think' keeps answers short and fast.
    no_think: bool = True


class RetrievalSettings(BaseModel):
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"
    device: str = "auto"
    chunk_tokens: int = 500
    chunk_overlap: float = 0.15
    rrf_k: int = 60
    candidates: int = 50
    rerank_top_k: int = 30
    final_k: int = 8
    graph_hops: int = 2
    # A question whose best reranked passage scores below this is refused.
    refusal_threshold: float = 0.15
    # A sentence whose best cited passage scores below this is marked unsupported.
    support_threshold: float = 0.25
    use_bm25: bool = True
    use_dense: bool = True
    use_graph: bool = True
    use_rerank: bool = True
    use_figures: bool = False


class SandboxSettings(BaseModel):
    timeout_s: int = 300
    memory_mb: int = 4096
    max_repairs: int = 3
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            "planetarycomputer.microsoft.com",
            "*.blob.core.windows.net",
            "sentinel-cogs.s3.us-west-2.amazonaws.com",
            "earth-search.aws.element84.com",
            "storage.googleapis.com",
        ]
    )


class Settings(BaseModel):
    tier: str = "cpu"
    paths: Paths = Field(default_factory=Paths)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    contact_email: str = "georag@example.org"


def _deep_update(base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings(root: Path | None = None) -> Settings:
    root = root or ROOT
    _load_dotenv(root / ".env")
    merged: dict[str, Any] = {}
    for name in ("default.yaml", "hardware.yaml"):
        path = root / "configs" / name
        if path.exists():
            _deep_update(merged, yaml.safe_load(path.read_text()) or {})

    env_map = {
        "GEORAG_LLM_BASE_URL": ("llm", "base_url"),
        "GEORAG_LLM_MODEL": ("llm", "model"),
        "GEORAG_EMBEDDING_MODEL": ("retrieval", "embedding_model"),
        "GEORAG_RERANKER_MODEL": ("retrieval", "reranker_model"),
        "GEORAG_DEVICE": ("retrieval", "device"),
    }
    for var, (section, key) in env_map.items():
        if var in os.environ:
            merged.setdefault(section, {})[key] = os.environ[var]
    if "CONTACT_EMAIL" in os.environ:
        merged["contact_email"] = os.environ["CONTACT_EMAIL"]
    if "GEORAG_DATA" in os.environ:
        merged.setdefault("paths", {})["data"] = os.environ["GEORAG_DATA"]
    merged.setdefault("paths", {}).setdefault("root", str(root))
    merged["paths"].setdefault("data", str(root / "data"))
    return Settings.model_validate(merged)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
