from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from georag.config import ROOT, Settings
from georag.corpus.build import read_documents, write_documents
from georag.llm import ScriptedLLM

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def built_settings(tmp_path_factory) -> Settings:
    """A settings object whose data dir holds the fixture corpus, indexed with the light models."""
    from georag.pipeline import build_index

    root = tmp_path_factory.mktemp("georag")
    (root / "corpus").mkdir()
    shutil.copy(ROOT / "corpus" / "glossary.yaml", root / "corpus" / "glossary.yaml")
    s = Settings.model_validate({"paths": {"root": str(root), "data": str(root / "data")}})
    s.paths.ensure()
    docs = read_documents(FIXTURES / "corpus.jsonl")
    write_documents(docs, s.paths.corpus / "documents.jsonl")
    build_index(s, light=True)
    return s


@pytest.fixture()
def engine(built_settings):
    from georag.engine import Engine

    return Engine(built_settings, light=True, llm=ScriptedLLM())
