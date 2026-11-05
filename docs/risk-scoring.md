# Risk scoring policy

The initial score is a deterministic weighted sum:

`R = 0.30S + 0.25C + 0.20D + 0.15T + 0.10A`

| Dimension | Weight | MVP input |
|---|---:|---|
| Security (S) | 0.30 | Security heuristic findings |
| Code quality (C) | 0.25 | Code-analysis findings |
| Dependency (D) | 0.20 | Unconstrained dependency findings |
| Testing (T) | 0.15 | Failed tests, missing evidence, low coverage |
| API compatibility (A) | 0.10 | Caller-provided score, 0–100 |

Severity points are info 5, low 15, medium 35, high 65 and critical 90. Multiple findings in one dimension combine with diminishing returns: `100 × (1 − product(1 − points/100))`.

Levels: low <40, medium 40–69, high >=70. Higher scores indicate higher release risk. API compatibility is provided by the caller; the MVP does not infer it from a diff.

Weights and thresholds are starter policy defaults, not empirically calibrated. The score is a prioritisation aid, not a probability of failure.
