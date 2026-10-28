from georag.agent.grounding import check_support, parse_citations, render_cited, split_cited
from georag.index.rerank import LexicalScorer
from georag.schemas import Chunk, Passage


def _p(text):
    return Passage(chunk=Chunk(chunk_id="c", doc_id="d", title="t", section="", text=text, domain="gis"))


def test_parse_citation_forms():
    assert parse_citations("1, 3") == [1, 3]
    assert parse_citations("2-4") == [2, 3, 4]
    assert parse_citations("5;5") == [5]


def test_split_cited_drops_invalid_numbers_and_moves_trailing_cites():
    s = split_cited("MNDWI uses SWIR [1]. NDWI uses NIR. [2] It is old [9].", {1, 2})
    assert [x.citations for x in s] == [[1], [2], []]
    assert s[1].text.startswith("NDWI uses NIR")


def test_support_check_flags_uncited_and_unsupported():
    sources = {1: _p("MNDWI uses the green and shortwave infrared bands of Sentinel-2.")}
    sents = split_cited(
        "MNDWI uses green and shortwave infrared bands [1]. Bananas are yellow [1]. No citation here.", {1}
    )
    ratio = check_support(sents, sources, LexicalScorer(), threshold=0.5)
    assert [s.supported for s in sents] == [True, False, False]
    assert abs(ratio - 1 / 3) < 1e-9
    assert "⚠" in render_cited(sents)


def test_coverage_notes_are_not_claims():
    sources = {1: _p("MNDWI uses the green and shortwave infrared bands of Sentinel-2.")}
    sents = split_cited(
        "MNDWI uses green and shortwave infrared bands [1]. The sources do not cover brackish lakes.", {1}
    )
    ratio = check_support(sents, sources, LexicalScorer(), threshold=0.5)
    assert ratio == 1.0 and all(s.supported for s in sents)
    assert "⚠" not in render_cited(sents)


def test_inline_citation_leaves_no_dangling_words():
    s = split_cited(
        "As described in [2], planes are fitted with RANSAC. The workflow ([3]) uses footprints.", {2, 3}
    )
    assert s[0].text == "As described, planes are fitted with RANSAC." and s[0].citations == [2]
    assert s[1].text == "The workflow uses footprints." and s[1].citations == [3]
