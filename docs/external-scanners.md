# External scanner integrations

## Semgrep Community Edition

When the `semgrep` executable is available on PATH, the security specialist
runs `semgrep scan --config auto --json --metrics=off --no-git-ignore` against
temporary files containing only added lines reconstructed from PR diff hunks.
Findings are mapped back to the original changed-file path and retain the
Semgrep rule ID, message, severity and line number.

Semgrep's `auto` configuration may retrieve community rules and therefore
requires network access for rule resolution. The scan is bounded by a 45-second
process timeout. The integration does not run repository scripts or build steps.

## OSV-Scanner v2

When `osv-scanner` is available and a Python requirements manifest is supplied,
the dependency specialist invokes:

```bash
osv-scanner scan source --format json --lockfile=/temporary/path/requirements.txt
```

The adapter parses OSV JSON results into dependency findings, including package,
version, advisory ID and severity when a CVSS score is available. A non-zero
scanner exit code does not discard valid JSON findings.

A resolved lockfile (for example `uv.lock`, `poetry.lock` or a fully pinned
requirements file) is preferable to an incomplete diff fragment. The current
GitHub PR ingestion only passes dependency lines extracted from changed
requirements files, so OSV coverage for that path is limited to those lines.

## Safety and failure behaviour

- Both scanners receive only temporary input files created by ReleaseGuard.
- Neither scanner is asked to execute submitted source code.
- Commands are argument arrays, never shell strings.
- Each process has a 45-second timeout and output parsing is bounded.
- Missing binaries, timeouts and invalid output are treated as scanner-unavailable
  results; local heuristic analysis continues.
- Scanner findings identify their source as `semgrep` or `osv_scanner`.
- Scanner availability and successful execution are not yet separately exposed
  in the API response; an empty finding list does not prove a clean scan.
