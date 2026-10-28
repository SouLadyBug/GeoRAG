"""Dense retrieval: Qwen3-Embedding vectors in a flat, exact inner-product index.

For corpora up to a few hundred thousand chunks an exact search over a float16 matrix is both
faster and simpler than an ANN server, and it makes metadata filtering trivial (a boolean mask).
The matrix is saved as ``.npy`` next to the chunk ids; Qdrant or LanceDB can replace it behind
the same ``search`` signature when the corpus grows.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from pathlib import Path
from typing import Protocol

import numpy as np

QUERY_INSTRUCTION = (
    "Given a question about GIS, remote sensing, LiDAR, digital twins or geospatial computer vision, "
    "retrieve scientific passages that answer it"
)


def cpu_has_fast_bf16() -> bool:
    """AMX or AVX-512 BF16 make bfloat16 inference ~3x faster than float32 on CPU; without them it is slower."""
    try:
        flags = Path("/proc/cpuinfo").read_text()
    except OSError:
        return False
    return "amx_bf16" in flags or "avx512_bf16" in flags


def model_dtype(device: str):
    import torch

    if device == "cuda":
        return torch.float16
    return torch.bfloat16 if cpu_has_fast_bf16() else torch.float32


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> np.ndarray: ...

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Qwen3-Embedding through sentence-transformers; queries get an instruction prompt."""

    def __init__(
        self, model_name: str, device: str = "auto", cache_dir: Path | None = None, max_seq_length: int = 640
    ):
        from sentence_transformers import SentenceTransformer

        device = resolve_device(device)
        kwargs = {"torch_dtype": model_dtype(device)}
        self.model = SentenceTransformer(
            model_name,
            device=device,
            cache_folder=str(cache_dir) if cache_dir else None,
            model_kwargs=kwargs,
            tokenizer_kwargs={"padding_side": "left"},  # type: ignore[call-arg]
        )
        self.model.max_seq_length = max_seq_length
        self.dim = int(self.model.get_embedding_dimension() or 0)
        self.name = model_name

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        # Sorting by length keeps padding (and CPU time) down; restore the order afterwards.
        order = np.argsort([len(t) for t in texts])
        vecs = self.model.encode(
            [texts[i] for i in order],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 200,
            convert_to_numpy=True,
        )
        out = np.empty_like(vecs)
        out[order] = vecs
        return out.astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        prompt = f"Instruct: {QUERY_INSTRUCTION}\nQuery: "
        return self.model.encode(
            texts, prompt=prompt, normalize_embeddings=True, convert_to_numpy=True
        ).astype(np.float32)


class HashingEmbedder:
    """Deterministic bag-of-hashed-trigrams embedder for tests and CPU-only CI.

    It has no semantic knowledge, but it is fast, has no downloads and exercises exactly the same
    index and fusion code paths as the real model.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"[a-z0-9]+", text.lower())
        grams = words + [f"{a}_{b}" for a, b in itertools.pairwise(words)]
        for g in grams:
            h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        return np.stack([self._embed(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self.embed_documents(texts)


class DenseIndex:
    def __init__(self, vectors: np.ndarray, ids: list[str], model_name: str = ""):
        self.vectors = vectors.astype(np.float16)
        self.ids = ids
        self.model_name = model_name

    def search(
        self, query_vec: np.ndarray, k: int = 50, allowed: np.ndarray | None = None
    ) -> list[tuple[str, float]]:
        sims = self.vectors.astype(np.float32) @ query_vec.astype(np.float32)
        if allowed is not None:
            sims = np.where(allowed, sims, -np.inf)
        k = min(k, len(self.ids))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self.ids[i], float(sims[i])) for i in top if np.isfinite(sims[i])]

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        np.save(path / "vectors.npy", self.vectors)
        (path / "ids.txt").write_text("\n".join(self.ids))
        (path / "model.txt").write_text(self.model_name)

    @classmethod
    def load(cls, path: Path) -> DenseIndex:
        vectors = np.load(path / "vectors.npy")
        ids = (path / "ids.txt").read_text().split("\n")
        model = (path / "model.txt").read_text() if (path / "model.txt").exists() else ""
        return cls(vectors, ids, model)
