# ReleaseGuard AI

**Evidence-backed release risk analysis and deployment governance for software pull requests.**

ReleaseGuard AI is a local-first prototype that analyses a submitted change set, reports traceable findings, calculates a transparent risk score, and prepares a human-reviewed release decision.

> **Current status:** A Python FastAPI local MVP is implemented, including read-only GitHub pull-request ingestion, concurrent local specialist agents, optional Semgrep CE / OSV-Scanner v2 adapters, and GitHub Actions JUnit / coverage evidence ingestion. Azure services, hosted LLM agents, durable storage, and production deployment remain future roadmap items.

## Implemented in this MVP

- Validated release submissions using Pydantic.
- Bounded local pattern checks for credential-like strings, risky configurations and selected code-quality issues.
- Optional Semgrep CE static-analysis and OSV-Scanner v2 dependency-advisory adapters (when their CLIs are installed).
- Dependency manifest checks for unconstrained Python requirements.
- Test evidence checks for failures, missing results, and low reported coverage.
- Structured findings with file/line evidence where available.
- Deterministic weighted risk score (not an LLM-generated score).
- Deployment checklist, rollback plan, and human approve/reject endpoints.
- Concurrent specialist-agent orchestration with per-agent execution metadata.
- GitHub Actions JUnit and Cobertura coverage artifact ingestion, including per-changed-file coverage findings.
- API, risk-engine, GitHub-ingestion, scanner-adapter and CI-evidence parser tests.

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

Example: `POST http://127.0.0.1:8000/api/github/octocat/Hello-World/pulls/1/analyse` (the PR must be open). The endpoint fetches metadata and up to 500 changed files, maps added lines from `requirements.txt` changes into the dependency check, and returns the usual ReleaseGuard assessment. GitHub file patches may be absent for binary or very large files; those files are listed but cannot be inspected by the current text-based heuristics. GitHub PR test results are not inferred by this diff-only endpoint. To include verified CI evidence, use the GitHub Actions endpoint described below.

## GitHub Actions test evidence

The CI workflow uploads a \`releaseguard-test-evidence\` artifact containing
JUnit test results and Cobertura \`coverage.xml\`. After a pull-request workflow
run completes, analyse that exact run with:

\`POST /api/github/{owner}/{repo}/pulls/{number}/runs/{run_id}/analyse\`

The endpoint verifies that the run is completed, was triggered by
\`pull_request\`, is associated with the requested PR, and matches the PR's
current head SHA. It then downloads the named artifact through the read-only
GitHub Actions API and parses JUnit totals plus overall and per-file coverage.
The API token needs Actions: read and Pull requests: read access for private
repositories. Artifacts are limited to 15 MB; individual XML reports are
limited to 5 MB. Artifacts expire after 14 days under the CI workflow settings.

Changed source files absent from the coverage report and changed source files
below 60% coverage produce separate test-intelligence findings. Coverage
filenames are matched by exact path, then by a unique suffix match. If the
artifact is missing or does not match the current PR head, the endpoint fails
rather than silently treating missing evidence as a passing test run.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/api/releases` | Create and analyse a release |
| POST | `/api/github/{owner}/{repo}/pulls/{number}/analyse` | Fetch and analyse an open GitHub PR (read-only) |
| POST | `/api/github/{owner}/{repo}/pulls/{number}/runs/{run_id}/analyse` | Analyse an open PR with its matching GitHub Actions test and coverage artifact |
| GET | `/api/releases/{id}` | Retrieve assessment |
| GET | `/api/releases/{id}/findings` | List findings |
| GET | `/api/releases/{id}/report` | Retrieve report and release plan |
| POST | `/api/releases/{id}/approve` | Record human approval |
| POST | `/api/releases/{id}/reject` | Record human rejection |

See [docs/github-actions-evidence.md](docs/github-actions-evidence.md) for the evidence format, validation checks and safety limits.

## Risk model

`R = 0.30S + 0.25C + 0.20D + 0.15T + 0.10A`

Dimensions are normalised to 0–100: security (S), code quality (C), dependency (D), testing (T), and API compatibility (A). Higher scores indicate higher risk. The score is computed deterministically in code. Weights and thresholds are initial policy defaults and have not been calibrated against a labelled benchmark. See [docs/risk-scoring.md](docs/risk-scoring.md).

## Safety boundaries

- Submitted code is analysed as text and is never executed.
- The prototype does not merge pull requests or deploy to production.
- Local heuristics can produce false positives and are not comprehensive security scanners. Optional Semgrep and OSV-Scanner integrations require their respective CLIs to be installed; unavailable tools are skipped without failing the local assessment.
- Semgrep scans only reconstructed added diff lines in temporary files. OSV-Scanner checks the supplied Python requirements manifest; a resolved lockfile is preferable for accurate dependency versions.
- The API currently has no authentication, authorisation, durable storage, or append-only audit log. Do not expose it to the public internet.
- GitHub pull-request and Actions evidence ingestion is read-only; no repository workflow is triggered or modified.
- Treat PR descriptions, comments, filenames and source code as untrusted input.

Install Semgrep CE and OSV-Scanner v2 separately to enable the optional scanner adapters. Semgrep uses its `scan --config auto --json` interface; OSV-Scanner uses `scan source --format json` against a temporary requirements file. Both calls have a 45-second timeout. See [docs/architecture.md](docs/architecture.md), [docs/security-model.md](docs/security-model.md), and [docs/risk-scoring.md](docs/risk-scoring.md).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). Planned increments include durable persistence, read-only GitHub integration, dedicated scanners, specialist agent orchestration, policy retrieval, frontend dashboard, Azure infrastructure, and measured benchmark evaluation.

## License

MIT. See [LICENSE](LICENSE).


## Specialist-agent workflow

Release assessments are now routed through a local supervisor that dispatches
four bounded specialists concurrently:

- **Code analysis** — flags security-sensitive code paths for focused review.
- **Security analysis** — checks submitted diff text for selected risky patterns
  and credential-like values.
- **Dependency analysis** — checks supported Python requirements input for
  unconstrained dependencies.
- **Test intelligence** — evaluates supplied test results and coverage evidence.

Each specialist follows a shared `run(request)` contract and returns structured
findings. The supervisor records execution duration and finding count for each
agent. If a specialist fails, the assessment fails rather than presenting a
partial result as complete. Results are returned in stable agent order.

This is a real, local orchestration layer, but the specialists currently use
bounded deterministic heuristics. It is **not yet an LLM-powered agent system**
and does not yet use Microsoft Agent Framework, Azure AI Foundry, or hosted
agent services. Submitted code is never executed.
