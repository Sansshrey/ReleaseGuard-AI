# ReleaseGuard AI

**Evidence-backed release risk analysis and deployment governance for software pull requests.**

ReleaseGuard AI is a local-first prototype that analyses a submitted change set, reports traceable findings, calculates a transparent risk score, and prepares a human-reviewed release decision.

> **Current status:** A Python FastAPI local MVP is implemented. Azure services, hosted LLM agents, live GitHub ingestion, and production deployment are future roadmap items—not current capabilities.

## Implemented in this MVP

- Validated release submissions using Pydantic.
- Bounded local pattern checks for credential-like strings and risky configurations.
- Dependency manifest checks for unconstrained Python requirements.
- Test evidence checks for failures, missing results, and low reported coverage.
- Structured findings with file/line evidence where available.
- Deterministic weighted risk score (not an LLM-generated score).
- Deployment checklist, rollback plan, and human approve/reject endpoints.
- API and risk-engine tests.

## Quick start

Requirements: Python 3.11+

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn releaseguard.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

Submit the sample release:

```bash
curl -X POST http://127.0.0.1:8000/api/releases \\
  -H "Content-Type: application/json" \\
  -d @data/sample-release.json
```

Use the returned `release_id` with `GET /api/releases/{id}/report`.

Run tests with:

```bash
pytest
```

## GitHub pull-request analysis

The MVP can fetch an **open** pull request and its changed-file patches using GitHub's read-only REST API. Set `GITHUB_TOKEN` in your local environment when analysing private repositories or when you need authenticated API rate limits. Use a fine-grained token restricted to the target repository with **Pull requests: read-only** permission. Never commit the token.

Start the API, then call:

`POST /api/github/{owner}/{repo}/pulls/{number}/analyse`

Example: `POST http://127.0.0.1:8000/api/github/octocat/Hello-World/pulls/1/analyse` (the PR must be open). The endpoint fetches metadata and up to 500 changed files, maps added lines from `requirements.txt` changes into the dependency check, and returns the usual ReleaseGuard assessment. GitHub file patches may be absent for binary or very large files; those files are listed but cannot be inspected by the current text-based heuristics. GitHub PR test results are not inferred: attach test evidence through the regular release request until a CI provider integration is implemented.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/api/releases` | Create and analyse a release |
| POST | `/api/github/{owner}/{repo}/pulls/{number}/analyse` | Fetch and analyse an open GitHub PR (read-only) |
| GET | `/api/releases/{id}` | Retrieve assessment |
| GET | `/api/releases/{id}/findings` | List findings |
| GET | `/api/releases/{id}/report` | Retrieve report and release plan |
| POST | `/api/releases/{id}/approve` | Record human approval |
| POST | `/api/releases/{id}/reject` | Record human rejection |

## Risk model

`R = 0.30S + 0.25C + 0.20D + 0.15T + 0.10A`

Dimensions are normalised to 0–100: security (S), code quality (C), dependency (D), testing (T), and API compatibility (A). Higher scores indicate higher risk. The score is computed deterministically in code. Weights and thresholds are initial policy defaults and have not been calibrated against a labelled benchmark. See [docs/risk-scoring.md](docs/risk-scoring.md).

## Safety boundaries

- Submitted code is analysed as text and is never executed.
- The prototype does not merge pull requests or deploy to production.
- Local pattern checks can produce false positives and are not comprehensive security scanners.
- The API currently has no authentication, authorisation, durable storage, or append-only audit log. Do not expose it to the public internet.
- Future GitHub ingestion should be read-only by default and verify webhook signatures.
- Treat PR descriptions, comments, filenames and source code as untrusted input.

See [docs/architecture.md](docs/architecture.md), [docs/security-model.md](docs/security-model.md), and [docs/risk-scoring.md](docs/risk-scoring.md).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). Planned increments include durable persistence, read-only GitHub integration, dedicated scanners, specialist agent orchestration, policy retrieval, frontend dashboard, Azure infrastructure, and measured benchmark evaluation.

## License

MIT. See [LICENSE](LICENSE).
