"""Bounded local analyzers; not a replacement for dedicated scanners."""
from __future__ import annotations

import re

from .models import Finding, ReleaseRequest, Severity

SECRET_PATTERNS = [
    (
        re.compile(r"""(?i)(api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['"][^'"]{8,}['"]"""),
        "Possible hard-coded credential",
    ),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private key material"),
]
SECURITY_PATTERNS = [
    (re.compile(r"(?i)verify\s*=\s*False"), "TLS certificate verification disabled"),
    (
        re.compile(r"""(?i)allow_origins\s*=\s*\[\s*['"]\*['"]"""),
        "Wildcard CORS origin configured",
    ),
    (
        re.compile(r"(?i)subprocess\.(?:run|Popen|call)\([^\n]*shell\s*=\s*True"),
        "Shell execution enabled",
    ),
    (re.compile(r"(?i)pickle\.loads\s*\("), "Potentially unsafe pickle deserialisation"),
    (re.compile(r"(?i)\b(?:eval|exec)\s*\("), "Dynamic code execution"),
]
CODE_PATTERNS = [
    (
        re.compile(r"(?m)^\s*except\s*:\s*(?:#.*)?$"),
        "Bare exception handler",
        Severity.MEDIUM,
        "Catch a specific exception type so unexpected failures are not hidden.",
    ),
    (
        re.compile(r"(?m)^\s*def\s+\w+\s*\([^\n)]*=\s*(?:\[\]|\{\}|set\(\))"),
        "Mutable default argument",
        Severity.MEDIUM,
        "Use None as the default and create a new mutable value inside the function.",
    ),
]


def _added_lines(patch: str) -> tuple[str, list[int]]:
    """Return added source text and its actual new-file line numbers."""
    added: list[str] = []
    line_numbers: list[int] = []
    new_line: int | None = None
    saw_hunk = False
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for raw in patch.splitlines():
        match = hunk.match(raw)
        if match:
            saw_hunk = True
            new_line = int(match.group(1))
        elif raw.startswith(("+++", "---")):
            continue
        elif raw.startswith("+") and new_line is not None:
            added.append(raw[1:])
            line_numbers.append(new_line)
            new_line += 1
        elif raw.startswith("-"):
            continue
        elif raw.startswith(" ") and new_line is not None:
            new_line += 1
    if not saw_hunk:
        raw_lines = patch.splitlines()
        return patch, list(range(1, len(raw_lines) + 1))
    return "\n".join(added), line_numbers


def _source_line(text: str, pos: int, line_numbers: list[int]) -> int | None:
    added_index = text.count("\n", 0, pos)
    return line_numbers[added_index] if added_index < len(line_numbers) else None


def analyse_security_changes(request: ReleaseRequest) -> list[Finding]:
    findings: list[Finding] = []
    for changed in request.changed_files:
        added, source_lines = _added_lines(changed.patch)
        for pattern, label in SECRET_PATTERNS:
            for match in pattern.finditer(added):
                findings.append(Finding(
                    agent="security_analysis", severity=Severity.CRITICAL,
                    category="possible_secret", title=label,
                    description="A credential-like value matched in an added diff line.",
                    recommendation="Remove the value and rotate it if genuine; use a managed secret store.",
                    file=changed.path, line=_source_line(added, match.start(), source_lines),
                    evidence=match.group(0)[:120], confidence=0.85,
                ))
        for pattern, label in SECURITY_PATTERNS:
            for match in pattern.finditer(added):
                findings.append(Finding(
                    agent="security_analysis", severity=Severity.HIGH,
                    category="risky_configuration", title=label,
                    description="A potentially unsafe pattern was found in added diff content.",
                    recommendation="Review the surrounding code and choose a safer configuration or API.",
                    file=changed.path, line=_source_line(added, match.start(), source_lines),
                    evidence=match.group(0)[:120], confidence=0.8,
                ))
    return findings


def analyse_code_changes(request: ReleaseRequest) -> list[Finding]:
    findings: list[Finding] = []
    for changed in request.changed_files:
        added, source_lines = _added_lines(changed.patch)
        if re.search(r"(?i)(auth|permission|role|token)", changed.path):
            findings.append(Finding(
                agent="code_analysis", severity=Severity.MEDIUM,
                category="security_sensitive_change", title="Security-sensitive file changed",
                description="The file path suggests authentication or authorisation logic changed.",
                recommendation="Add focused tests for permitted and denied access paths.",
                file=changed.path, evidence=f"Changed path: {changed.path}", confidence=0.65,
            ))
        for pattern, label, severity, recommendation in CODE_PATTERNS:
            for match in pattern.finditer(added):
                findings.append(Finding(
                    agent="code_analysis", severity=severity,
                    category="code_quality", title=label,
                    description="A maintainability or error-handling risk was found in added diff content.",
                    recommendation=recommendation, file=changed.path,
                    line=_source_line(added, match.start(), source_lines),
                    evidence=match.group(0)[:120], confidence=0.8,
                ))
    return findings


def analyse_changes(request: ReleaseRequest) -> list[Finding]:
    """Compatibility helper returning findings from both code and security analyzers."""
    return analyse_code_changes(request) + analyse_security_changes(request)


def analyse_dependencies(manifest: str | None, ecosystem: str) -> list[Finding]:
    if not manifest or ecosystem.lower() not in {"python", "pip", "requirements.txt"}:
        return []
    findings = []
    for number, raw in enumerate(manifest.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        if not re.search(r"(==|~=|>=|<=|!=)", line):
            findings.append(Finding(
                agent="dependency_analysis", severity=Severity.LOW,
                category="unpinned_dependency", title="Dependency version is not constrained",
                description=f"'{line[:100]}' has no visible version constraint.",
                recommendation="Constrain versions and review updates through a lockfile.",
                file="requirements.txt", line=number, evidence=line[:120], confidence=0.95,
            ))
    return findings


def analyse_tests(request: ReleaseRequest) -> list[Finding]:
    summary = request.test_summary
    findings = []
    if summary.failed:
        findings.append(Finding(
            agent="test_intelligence", severity=Severity.HIGH,
            category="failing_tests", title="Test failures reported",
            description=f"{summary.failed} of {summary.total} reported tests failed.",
            recommendation="Resolve failures or document an explicit, reviewed waiver.",
            evidence=f"passed={summary.passed}, failed={summary.failed}, total={summary.total}",
        ))
    if summary.total == 0:
        findings.append(Finding(
            agent="test_intelligence", severity=Severity.MEDIUM,
            category="missing_test_evidence", title="No test execution evidence supplied",
            description="No test execution results were attached to this release.",
            recommendation="Run relevant unit, integration and regression tests and attach results.",
            evidence="test_summary.total = 0",
        ))
    if summary.coverage_files:
        coverage_by_path = {
            path.replace("\\", "/").lstrip("./"): value
            for path, value in summary.coverage_files.items()
        }
        for changed in request.changed_files:
            path = changed.path.replace("\\", "/").lstrip("./")
            if path.endswith((".py", ".cs", ".js", ".jsx", ".ts", ".tsx", ".go", ".java")):
                coverage = coverage_by_path.get(path)
                if coverage is None:
                    matches = [
                        value for report_path, value in coverage_by_path.items()
                        if report_path.endswith("/" + path) or path.endswith("/" + report_path)
                    ]
                    coverage = matches[0] if len(matches) == 1 else None
                if coverage is None:
                    findings.append(Finding(
                        agent="test_intelligence", severity=Severity.MEDIUM,
                        category="changed_file_missing_coverage",
                        title="Changed source file is absent from coverage report",
                        description=f"No per-file coverage entry matched '{changed.path}'.",
                        recommendation="Add or configure tests so this changed module is included in coverage measurement.",
                        file=changed.path, evidence=f"coverage report did not include {changed.path}",
                        confidence=0.85, source="github_actions",
                    ))
                elif coverage < 60:
                    findings.append(Finding(
                        agent="test_intelligence", severity=Severity.MEDIUM,
                        category="changed_file_low_coverage",
                        title="Changed source file has low test coverage",
                        description=f"Coverage for '{changed.path}' is {coverage:.1f}%.",
                        recommendation="Add focused tests for the changed module and review uncovered branches.",
                        file=changed.path, evidence=f"per_file_coverage={coverage:.2f}%",
                        confidence=0.95, source="github_actions",
                    ))
    if summary.coverage_percent is not None and summary.coverage_percent < 60:
        findings.append(Finding(
            agent="test_intelligence", severity=Severity.MEDIUM,
            category="low_coverage", title="Reported test coverage is below 60%",
            description=f"Reported coverage is {summary.coverage_percent:.1f}%.",
            recommendation="Add tests for changed modules and review coverage exclusions.",
            evidence=f"coverage_percent={summary.coverage_percent}",
        ))
    return findings
