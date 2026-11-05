# Agent orchestration

## Current implementation

`ReleaseSupervisor` dispatches four specialist agents concurrently using a
bounded thread pool. Each agent implements the `SpecialistAgent` contract:
a stable name and a `run(ReleaseRequest) -> list[Finding]` method.

The current specialists are:

| Specialist | Responsibility | Current implementation |
|---|---|---|
| Code analysis | Highlight sensitive code changes | File-path heuristics |
| Security analysis | Detect selected risky patterns and credential-like values | Regex heuristics over diff text |
| Dependency analysis | Identify unconstrained Python requirements | Manifest parser heuristics |
| Test intelligence | Identify failures, missing evidence and low coverage | Structured test-summary rules |

The supervisor records status, elapsed milliseconds and finding count. It
returns results in configured agent order even though work runs concurrently.
A specialist exception aborts the assessment; partial results are not saved.

## Boundaries

- Submitted source code and build scripts are treated as untrusted text.
- No submitted code is executed.
- No specialist can approve or deploy a release.
- Risk scoring is performed separately by the deterministic risk module.
- The current local specialists do not call an LLM or external service.

## Next evolution

1. Add independent analyzers and typed evidence contracts per specialist.
2. Add timeout, cancellation and retry policies with bounded budgets.
3. Add evaluation fixtures and per-agent precision/recall measurements.
4. Introduce Microsoft Agent Framework behind the same interfaces only after
   validating the supported SDK and preserving the deterministic local mode.
5. Add durable run state and audit events before any hosted deployment.
