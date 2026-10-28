"""On-disk index layout and loading.

``data/index/`` holds ``chunks.parquet`` plus one folder per retriever (``bm25/``, ``dense/``,
``graph/``). Every stage writes a ``.done`` marker with its inputs' fingerprint so ``make index``
can be re-run safely and only redoes stages whose inputs changed.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from georag.schemas import Chunk


def save_chunks(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([c.model_dump() for c in chunks]).to_parquet(path, index=False)


def load_chunks(path: Path) -> list[Chunk]:
    df = pd.read_parquet(path)
    records = df.astype(object).where(df.notna(), None).to_dict("records")
    return [Chunk.model_validate(r) for r in records]


def fingerprint(*parts: str | Path) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path) and p.exists():
            if p.is_file():
                h.update(p.read_bytes())
            else:
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        h.update(f.name.encode())
                        h.update(str(f.stat().st_size).encode())
        else:
            h.update(str(p).encode())
    return h.hexdigest()[:16]


class Stage:
    """Run a pipeline stage once per input fingerprint and log its wall time."""

    def __init__(self, name: str, out_dir: Path, log_path: Path):
        self.name = name
        self.out_dir = out_dir
        self.log_path = log_path

    @property
    def marker(self) -> Path:
        return self.out_dir / ".done"

    def is_done(self, fp: str) -> bool:
        return self.marker.exists() and json.loads(self.marker.read_text()).get("fingerprint") == fp

    def run(self, fp: str, fn: Callable[[], dict | None], force: bool = False) -> dict:
        if not force and self.is_done(fp):
            return json.loads(self.marker.read_text())
        t0 = time.perf_counter()
        info = fn() or {}
        seconds = time.perf_counter() - t0
        record = {"stage": self.name, "fingerprint": fp, "seconds": round(seconds, 1), **info}
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.marker.write_text(json.dumps(record, indent=2))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps({**record, "finished": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
        return record
