from evals.runners.rag_ablation import run


def test_ablation_is_complete_and_provenance_is_explicit() -> None:
    result = run()
    assert result["metadata"]["data_origin"] == "synthetic"
    assert result["metadata"]["jobs"] == 90
    assert set(result["overall"]) == {"dense_only", "lexical_only", "hybrid_rrf"}
    assert len(result["rows"]) == 270
    assert all(0 <= metrics["evidence_recall_at_5"] <= 1 for metrics in result["overall"].values())
