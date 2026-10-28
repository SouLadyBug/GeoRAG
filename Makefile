.PHONY: setup hardware models llm corpus index bench eval demos web site serve dev test lint typecheck clean

PY := uv run
LLM_PORT ?= 8080

setup:            ## Python env, web deps, hardware tier
	uv sync --extra models --extra llamacpp --group dev
	cd web && npm ci
	$(PY) georag hardware

hardware:
	$(PY) georag hardware

models:           ## pull the generator for the detected tier (Ollama)
	$(PY) python scripts/pull_models.py

llm:              ## CPU fallback: serve a GGUF model with llama.cpp on :$(LLM_PORT)
	$(PY) python scripts/serve_llamacpp.py --port $(LLM_PORT)

corpus:
	$(PY) georag corpus

index: corpus     ## corpus, chunks, BM25, dense vectors, knowledge graph
	$(PY) georag index

bench:            ## generate GeoRAG-Bench questions (resumable)
	$(PY) python scripts/build_bench.py

eval: bench       ## run the benchmark and write results/
	$(PY) python scripts/run_eval.py

demos:            ## record showcase runs into web/public/demo
	$(PY) georag demos

site:             ## export site data and build the static showcase
	$(PY) python scripts/export_site.py
	cd web && npm run build

serve:            ## API + web app on http://127.0.0.1:8000
	cd web && npm run build
	$(PY) georag serve

dev:              ## API on :8000 and Vite dev server on :5173
	$(PY) georag serve & cd web && npm run dev

test:
	$(PY) pytest -q

lint:
	$(PY) ruff check src tests scripts
	$(PY) ruff format --check src tests scripts

typecheck:
	$(PY) mypy
	cd web && npm run typecheck

clean:
	rm -rf data/index data/runs web/dist
