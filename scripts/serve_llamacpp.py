"""Serve a GGUF model through llama.cpp's OpenAI-compatible server (CPU tier, no Ollama needed).

Downloads the model from the Hugging Face Hub on first use and points configs/hardware.yaml at it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "qwen3-4b": ("unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
    "qwen3-1.7b": ("unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3-4b", choices=sorted(MODELS))
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--no-config", action="store_true", help="do not touch configs/hardware.yaml")
    args = ap.parse_args()

    from huggingface_hub import hf_hub_download

    repo, filename = MODELS[args.model]
    path = hf_hub_download(repo, filename, cache_dir=str(ROOT / "data" / "models"))
    if not args.no_config:
        hw_path = ROOT / "configs" / "hardware.yaml"
        hw = yaml.safe_load(hw_path.read_text()) if hw_path.exists() else {}
        hw.setdefault("llm", {}).update(
            {
                "base_url": f"http://127.0.0.1:{args.port}/v1",
                "model": args.model,
                "no_think": args.model != "qwen3-4b",
            }
        )
        hw_path.write_text(yaml.safe_dump(hw, sort_keys=False))
    cmd = [
        sys.executable,
        "-m",
        "llama_cpp.server",
        "--model",
        path,
        "--model_alias",
        args.model,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--n_ctx",
        str(args.ctx),
        "--n_threads",
        str(args.threads),
        "--n_batch",
        "512",
    ]
    print(" ".join(cmd), flush=True)
    os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
