import pytest

from releaseguard.benchmark import evaluate


def test_benchmark_scores_perfect_predictions_and_valid_evidence():
    dataset = [{
        "case_id": "case-1",
        "release_request": {"changed_files": [{"path": "src/a.py", "patch": "verify=False"}]},
        "expected_findings": [{"severity": "high", "category": "tls", "file": "src/a.py", "evidence": "verify=False"}],
        "allowed_policy_ids": ["security-baseline"],
    }, {
        "case_id": "case-2", "release_request": {"changed_files": []},
        "expected_findings": [], "allowed_policy_ids": [],
    }]
    predictions = [{
        "case_id": "case-1",
        "findings": [{"severity": "high", "category": "tls", "file": "src/a.py",
                      "evidence": "verify=False", "policy_references": ["security-baseline"]}],
        "latency_ms": 100, "estimated_cost_usd": 0.001,
    }, {"case_id": "case-2", "findings": []}]
    report = evaluate(dataset, predictions)
    assert report["finding_f1"] == 1.0
    assert report["exact_case_accuracy"] == 1.0
    assert report["evidence_validity"] == 1.0
    assert report["policy_citation_validity"] == 1.0
    assert report["latency_ms"]["p50"] == 100


def test_benchmark_counts_false_positives_and_invalid_evidence():
    dataset = [{
        "case_id": "case-1", "release_request": {"changed_files": [{"patch": "safe"}]},
        "expected_findings": [], "allowed_policy_ids": [],
    }]
    predictions = [{
        "case_id": "case-1", "findings": [{
            "severity": "critical", "category": "fabricated", "file": "src/x.py",
            "evidence": "not in patch", "policy_references": ["made-up"],
        }]
    }]
    report = evaluate(dataset, predictions)
    assert report["finding_precision"] == 0.0
    assert report["finding_recall"] == 0.0
    assert report["evidence_validity"] == 0.0
    assert report["policy_citation_validity"] == 0.0


def test_benchmark_rejects_unknown_prediction_case():
    with pytest.raises(ValueError, match="unknown case"):
        evaluate([{"case_id": "known", "expected_findings": []}],
                 [{"case_id": "unknown", "findings": []}])


def test_committed_synthetic_dataset_contains_one_hundred_cases():
    import json
    from pathlib import Path

    dataset_path = Path(__file__).parents[1] / "data" / "benchmark" / "release_cases.jsonl"
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 100
    assert len({row["case_id"] for row in rows}) == 100
