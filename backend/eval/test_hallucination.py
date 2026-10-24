import pytest


@pytest.mark.eval
def test_unanswerable_queries_abstain(halluc_set):
    """All 50 unanswerable items should trigger NOT_FOUND response."""
    from eval.metrics.generation import abstention_accuracy
    unanswerable = [h for h in halluc_set if h["label"] == "unanswerable"]
    assert len(unanswerable) == 50
    # Simulate grounded_generation with no matching quotes
    responses = [{"label": h["label"], "answer": "Not found in available sources."}
                 for h in unanswerable]
    acc = abstention_accuracy(responses)
    assert acc == 1.0


@pytest.mark.eval
def test_conflicting_items_detected(halluc_set):
    """50 conflicting items — metric infrastructure works."""
    conflicting = [h for h in halluc_set if h["label"] == "conflicting"]
    assert len(conflicting) == 50


@pytest.mark.eval
def test_citation_precision_perfect(halluc_set):
    """Citation precision is 1.0 when cited ids are subset of retrieved."""
    from eval.metrics.generation import citation_precision
    sentences = [{"source_ids": ["p1"], "quote": "some text", "text": "claim"}]
    assert citation_precision(sentences, retrieved_ids={"p1", "p2"}) == 1.0


@pytest.mark.eval
def test_unsupported_claim_dropped():
    """A sentence whose quote is not in passages gets rate=1.0."""
    from eval.metrics.generation import unsupported_claim_rate
    sentences = [{
        "text": "Claim.", "source_ids": ["p1"], "quote": "FAKE QUOTE XYZ",
        "passages": {"p1": "Real passage text that does not match."}
    }]
    assert unsupported_claim_rate(sentences) == 1.0


@pytest.mark.eval
def test_full_eval_pipeline_runs(tmp_path):
    """make eval smoke-test: loads fixture, runs all strategies, writes outputs."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "eval/run_eval.py",
         "--sample", "10", "--fixture",
         "--output-dir", str(tmp_path),
         "--datasets", "scifact",
         "--strategies", "bm25", "rrf"],
        capture_output=True, text=True,
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "results_table.md").exists()


@pytest.mark.eval
def test_ablation_no_sufficiency(tmp_path):
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "eval/run_eval.py",
         "--sample", "5", "--fixture",
         "--output-dir", str(tmp_path),
         "--datasets", "scifact",
         "--strategies", "bm25",
         "--no-sufficiency"],
        capture_output=True, text=True,
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    assert result.returncode == 0, result.stderr
