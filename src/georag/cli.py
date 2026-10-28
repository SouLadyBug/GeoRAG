"""Command-line interface: ``georag <command>``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from georag.config import ROOT, get_settings

app = typer.Typer(
    add_completion=False, help="GeoRAG Copilot — a local retrieval-augmented agent for geospatial research."
)
console = Console()


def _engine(light: bool = False):
    from georag.engine import Engine

    return Engine(get_settings(), light=light)


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING, format="%(asctime)s %(name)s %(message)s"
    )


@app.command()
def hardware() -> None:
    """Detect the GPU and write configs/hardware.yaml with the matching model tier."""
    from georag.hardware import write_hardware_config

    cfg = write_hardware_config(ROOT / "configs" / "hardware.yaml")
    console.print_json(json.dumps(cfg))


@app.command()
def corpus(
    source: str = typer.Option("arxiv", help="arxiv (CC0 metadata snapshot) or openalex (needs an API key)"),
    force: bool = False,
) -> None:
    """Collect papers, technical docs, the dataset catalogue and the glossary; write the manifest."""
    from georag.pipeline import build_corpus

    console.print_json(json.dumps(build_corpus(get_settings(), source, force)))


@app.command()
def index(
    light: bool = typer.Option(False, help="hashing embedder, no model downloads (CI)"), force: bool = False
) -> None:
    """Chunk the corpus and build the BM25, dense and graph indexes."""
    from georag.pipeline import build_index

    console.print_json(json.dumps(build_index(get_settings(), light, force), default=str))


@app.command()
def ask(question: str, light: bool = False) -> None:
    """Answer a question with citations."""
    res = _engine(light).ask_agent.run(question)
    console.print(Markdown(res.answer))
    for c in res.citations:
        console.print(f"[dim][{c.n}] {c.title} ({c.year or '-'}) {c.url or ''}[/dim]")
    if res.faithfulness is not None:
        console.print(f"[green]supported sentences: {res.faithfulness:.0%}[/green]")


@app.command()
def design(question: str) -> None:
    """Write a cited study-design brief."""
    res = _engine().design_agent.run(question)
    console.print(Markdown(res.markdown))


@app.command()
def explore(question: str) -> None:
    """Show how concepts connect in the knowledge graph."""
    res = _engine().explore_agent.run(question)
    console.print(f"seeds: {', '.join(res.seeds)}  ·  {len(res.nodes)} nodes, {len(res.edges)} edges")
    for p in res.paths:
        console.print(" → ".join(p))
    if res.summary:
        console.print(Markdown(res.summary))


@app.command()
def analyze(question: str, reference: bool = False) -> None:
    """Plan, generate and run an Earth-observation analysis."""
    res = _engine().analyze_agent.run(
        question, emit=lambda e: console.print(f"[dim]{e['type']}[/dim]"), reference=reference
    )
    console.print(res.explanation)
    console.print(f"run folder: {get_settings().paths.runs / res.run_id}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, light: bool = False) -> None:
    """Start the API and the web app."""
    import uvicorn

    from georag.server import create_app

    uvicorn.run(create_app(light=light), host=host, port=port)


@app.command()
def demos(out: Path = ROOT / "web" / "public" / "demo") -> None:
    """Pre-generate the showcase runs (the same scenarios double as integration tests)."""
    from georag.showcase import generate_demos

    generate_demos(_engine(), out)


if __name__ == "__main__":
    app()
