from georag.index.fusion import reciprocal_rank_fusion


def test_rrf_rewards_agreement():
    fused = reciprocal_rank_fusion({"bm25": ["a", "b", "c"], "dense": ["b", "a", "d"]}, k=60)
    ids = [f[0] for f in fused]
    assert set(ids[:2]) == {"a", "b"}
    assert ids.index("d") > ids.index("a")


def test_rrf_scores_match_formula_and_ranks_recorded():
    fused = dict((d, (s, r)) for d, s, r in reciprocal_rank_fusion({"x": ["a"], "y": ["b", "a"]}, k=10))
    assert abs(fused["a"][0] - (1 / 11 + 1 / 12)) < 1e-12
    assert fused["a"][1] == {"x": 1, "y": 2}


def test_rrf_weights_and_duplicates():
    fused = reciprocal_rank_fusion({"x": ["a", "a", "b"], "g": ["b"]}, k=60, weights={"g": 0.0})
    assert [f[0] for f in fused] == ["a", "b"]
