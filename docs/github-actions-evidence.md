# GitHub Actions test evidence

ReleaseGuard can attach test and coverage evidence from a completed GitHub
Actions pull-request run.

## CI artifact contract

The repository CI workflow produces:

- \`junit.xml\` using pytest's JUnit XML reporter.
- \`coverage.xml\` using pytest-cov's Cobertura-compatible XML reporter.
- A single artifact named \`releaseguard-test-evidence\`, retained for 14 days.

The parser reads JUnit \`testsuite\` / \`testsuites\` counters and Cobertura
\`coverage\` / \`class\` entries. It does not execute test code or workflow steps.

## API flow

Call:

\`POST /api/github/{owner}/{repo}/pulls/{number}/runs/{run_id}/analyse\`

ReleaseGuard fetches the PR diff and checks the workflow run. The run must:

1. Be completed.
2. Have event type \`pull_request\`.
3. Be associated with the requested pull request number.
4. Have the same head SHA as the current PR revision.
5. Contain an unexpired \`releaseguard-test-evidence\` artifact.

The fine-grained GitHub token requires Pull requests: read and Actions: read
permissions for private repositories. Public repositories may be readable
without a token, subject to GitHub rate limits.

## Findings

JUnit counters populate total, passed, failed and skipped test counts. Overall
coverage populates \`coverage_percent\`. Per-file coverage is matched to changed
source paths by exact match or unique suffix match.

- Changed source file below 60% coverage: \`changed_file_low_coverage\`.
- Changed source file absent from report: \`changed_file_missing_coverage\`.
- Overall coverage below 60%: \`low_coverage\`.
- Failed or errored tests: \`failing_tests\`.

## Resource and parsing limits

- Downloaded ZIP: 15 MB maximum.
- Expanded ZIP contents: 20 MB maximum.
- At most 100 files in the ZIP.
- Each parsed XML report: 5 MB maximum.
- DTD and entity declarations are rejected.
- ZIP entries are inspected in memory; paths are never extracted to disk.
- Missing, expired, stale or malformed evidence fails the evidence endpoint
  rather than being interpreted as passing tests.

## Known limitations

The parser currently supports JUnit XML and Cobertura-style XML coverage.
It does not yet ingest pytest JSON, LCOV, JaCoCo, TRX or SARIF reports. Coverage
path matching can be ambiguous in monorepos; ambiguous matches are left
unmatched rather than guessed.
