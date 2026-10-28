from georag.index.chunking import approx_tokens, chunk_document, chunk_text, split_sentences
from georag.schemas import Document


def test_short_text_is_one_chunk():
    assert chunk_text("A short abstract about LiDAR.") == ["A short abstract about LiDAR."]


def test_long_text_respects_budget_and_overlap():
    para = " ".join(f"Sentence number {i} talks about Sentinel-2 water mapping." for i in range(200))
    chunks = chunk_text(para, max_tokens=120, overlap=0.15)
    assert len(chunks) > 5
    assert all(approx_tokens(c) <= 120 + 15 for c in chunks)
    # consecutive chunks share their boundary sentence(s)
    first_tail = split_sentences(chunks[0])[-1]
    assert first_tail in chunks[1]


def test_sections_are_not_crossed():
    doc = Document(
        doc_id="d",
        source="docs",
        title="T",
        text="",
        domain="docs",
        sections=[("Intro", "Alpha " * 50), ("Method", "Beta " * 50)],
    )
    chunks = chunk_document(doc, max_tokens=500)
    assert [c.section for c in chunks] == ["Intro", "Method"]
    assert "Beta" not in chunks[0].text


def test_abbreviations_do_not_split_sentences():
    s = split_sentences("Water indices, e.g. MNDWI, help. Smith et al. showed this. Next sentence.")
    assert len(s) == 3
