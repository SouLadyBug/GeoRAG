# Contributing

Thanks for your interest in GeoRAG Copilot.

## Development setup

```bash
uv sync --group dev          # add --extra models --extra llamacpp for the full stack
cd web && npm ci && cd ..
uv run pre-commit install
```

## Before opening a pull request

```bash
make lint        # ruff check + format check
make typecheck   # mypy + tsc
make test        # pytest on the fixture corpus with a scripted LLM (no GPU, no network)
```

Tests that need the internet (`-m network`) or downloaded models (`-m models`) are skipped by
default; run them with `uv run pytest -m network`.

## Guidelines

- Keep the agent loop explicit: plain Python and Pydantic models, every step logged.
- Generated analysis code must come from templates in `src/georag/agent/templates/` and pass
  `sandbox.static_check`. New templates need a rendering test in `tests/test_geo.py`.
- Never commit documents, extracted text, model weights or indexes; only scripts, the manifest
  and results. Every new corpus source must record a licence per document.
- Numbers on the website and in the README must come from files in `results/`.

## Adding a corpus source

Write a collector that returns `georag.schemas.Document` objects (see `src/georag/corpus/`),
register it in `georag.pipeline.build_corpus`, and add its licence to the README table.
