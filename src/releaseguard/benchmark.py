"""Offline benchmark metrics for ReleaseGuard model predictions."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: each row must be an object")
            records.append(value)
    return records


def _identity(finding: dict[str, Any]) -> tuple[str, str]:
    return str(finding.get("category", "")), str(finding.get("file") or "")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def evaluate(dataset: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    expected_by_id = {row["case_id"]: row for row in dataset}
    if len(expected_by_id) != len(dataset):
        raise ValueError("Dataset contains duplicate case_id values")
    predicted_by_id = {row["case_id"]: row for row in predictions}
    if len(predicted_by_id) != len(predictions):
        raise ValueError("Predictions contain duplicate case_id values")
    unknown = set(predicted_by_id) - set(expected_by_id)
    if unknown:
        raise ValueError(f"Predictions contain unknown case IDs: {sorted(unknown)[:5]}")

    true_positive = false_positive = false_negative = 0
    exact_cases = 0
    evidence_valid = evidence_total = 0
    citation_valid = citation_total = 0
    severity_labels = sorted({
        finding["severity"]
        for row in dataset for finding in row.get("expected_findings", [])
    } | {
        finding.get("severity", "")
        for row in predictions for finding in row.get("findings", [])
    } - {""})
    severity_counts = {label: {"tp": 0, "fp": 0, "fn": 0} for label in severity_labels}
    severity_correct = severity_total = 0
    latencies: list[float] = []
    costs: list[float] = []

    for case_id, expected_row in expected_by_id.items():
        predicted_row = predicted_by_id.get(case_id, {})
        expected = {_identity(item): item for item in expected_row.get("expected_findings", [])}
        predicted = {_identity(item): item for item in predicted_row.get("findings", [])}
        expected_keys, predicted_keys = set(expected), set(predicted)
        matched = expected_keys & predicted_keys
        true_positive += len(matched)
        false_positive += len(predicted_keys - expected_keys)
        false_negative += len(expected_keys - predicted_keys)
        if expected_keys == predicted_keys:
            exact_cases += 1

        for key in expected_keys | predicted_keys:
            expected_severity = expected.get(key, {}).get("severity", "none")
            predicted_severity = predicted.get(key, {}).get("severity", "none")
            severity_total += 1
            severity_correct += expected_severity == predicted_severity
            for label in severity_labels:
                counts = severity_counts[label]
                if expected_severity == label and predicted_severity == label:
                    counts["tp"] += 1
                elif expected_severity != label and predicted_severity == label:
                    counts["fp"] += 1
                elif expected_severity == label and predicted_severity != label:
                    counts["fn"] += 1

        patches = [
            str(item.get("patch", ""))
            for item in expected_row.get("release_request", {}).get("changed_files", [])
        ]
        allowed_policies = set(expected_row.get("allowed_policy_ids", []))
        for finding in predicted_row.get("findings", []):
            evidence_total += 1
            evidence = finding.get("evidence")
            evidence_valid += isinstance(evidence, str) and bool(evidence) and any(evidence in patch for patch in patches)
            references = finding.get("policy_references", [])
            if isinstance(references, list):
                citation_total += len(references)
                citation_valid += sum(isinstance(ref, str) and ref in allowed_policies for ref in references)

        if isinstance(predicted_row.get("latency_ms"), (int, float)):
            latencies.append(float(predicted_row["latency_ms"]))
        if isinstance(predicted_row.get("estimated_cost_usd"), (int, float)):
            costs.append(float(predicted_row["estimated_cost_usd"]))

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    per_severity = {}
    f1_values = []
    for label, counts in severity_counts.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0.0
        score = 2 * p * r / (p + r) if p + r else 0.0
        per_severity[label] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(score, 4)}
        f1_values.append(score)

    return {
        "dataset_cases": len(dataset),
        "prediction_cases": len(predictions),
        "finding_precision": round(precision, 4),
        "finding_recall": round(recall, 4),
        "finding_f1": round(f1, 4),
        "severity_accuracy": round(severity_correct / severity_total, 4) if severity_total else None,
        "severity_macro_f1": round(sum(f1_values) / len(f1_values), 4) if f1_values else None,
        "exact_case_accuracy": round(exact_cases / len(dataset), 4) if dataset else None,
        "evidence_validity": round(evidence_valid / evidence_total, 4) if evidence_total else None,
        "policy_citation_validity": round(citation_valid / citation_total, 4) if citation_total else None,
        "latency_ms": {"p50": _percentile(latencies, 0.50), "p95": _percentile(latencies, 0.95)},
        "estimated_cost_usd_total": round(sum(costs), 6) if costs else None,
        "measured_latency_samples": len(latencies),
        "measured_cost_samples": len(costs),
        "notes": "Only metrics supplied in prediction JSONL are measured; missing predictions count as no findings."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ReleaseGuard predictions against labelled synthetic cases.")
    parser.add_argument("--dataset", default="data/benchmark/release_cases.jsonl")
    parser.add_argument("--predictions", required=True, help="JSONL predictions keyed by case_id")
    parser.add_argument("--output", help="Optional path to write the JSON report")
    args = parser.parse_args()
    report = evaluate(load_jsonl(args.dataset), load_jsonl(args.predictions))
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
