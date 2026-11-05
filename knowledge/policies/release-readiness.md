# Release Readiness Standard

## Test evidence
A release assessment should use test results tied to the exact commit being assessed. Missing test evidence is unknown, not a passing result. Record total, passed, failed, skipped, and coverage values with their source.

## Coverage interpretation
Coverage is a signal, not proof of correctness. Review coverage for changed critical paths and inspect tests for meaningful assertions. Avoid treating a single repository-wide percentage as sufficient evidence.

## Rollback readiness
Before release, identify the last known-good artifact or revision, the rollback owner, and the steps to verify service health after rollback. Do not claim rollback is executable unless the deployment platform and procedure are configured.

## Human release approval
High-impact production changes require explicit review by an authorised human. An automated analysis may recommend a decision but must not approve or deploy a release. Record the reviewer, timestamp, decision, and rationale.
