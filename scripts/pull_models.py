"""Pull the generator for the detected tier into Ollama, falling back to the next tag if a tag is missing."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if not shutil.which("ollama"):
        print("ollama is not installed; use `make llm` for the llama.cpp CPU server instead")
        return 1
    hw = yaml.safe_load((ROOT / "configs" / "hardware.yaml").read_text())
    candidates = [hw["llm"]["model"], *hw.get("models", {}).get("fallbacks", [])]
    for tag in candidates:
        print(f"ollama pull {tag}")
        if subprocess.run(["ollama", "pull", tag]).returncode == 0:
            if tag != hw["llm"]["model"]:
                hw["llm"]["model"] = tag
                (ROOT / "configs" / "hardware.yaml").write_text(yaml.safe_dump(hw, sort_keys=False))
                print(f"tier default unavailable; using {tag} (configs/hardware.yaml updated)")
            return 0
    print("none of the tier's models could be pulled", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
