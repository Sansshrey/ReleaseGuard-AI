"""Bounded local heuristics; these are not a replacement for dedicated scanners."""
import re
from .models import Finding, ReleaseRequest, Severity

SECRET_PATTERNS = [
    (re.compile(r"""(?i)(api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['"][^'"]{8,}['"]"""), "Possible hard-coded credential"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private key material"),
]
RISKY_PATTERNS = [
    (re.compile(r"(?i)verify\s*=\s*False"), "TLS certificate verification disabled"),
    (re.compile(r"""(?i)allow_origins\s*=\s*\[\s*['"]\*['"]"""), "Wildcard CORS origin configured"),
    (re.compile(r"(?i)subprocess\.(?:run|Popen|call)\([^\n]*shell\s*=\s*True"), "Shell execution enabled"),
    (re.compile(r"(?i)pickle\.loads\s*\("), "Potentially unsafe pickle deserialisation"),
]

def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1

def analyse_changes(request: ReleaseRequest) -> list[Finding]:
    findings: list[Finding] = []
    for changed in request.changed_files:
        for pattern, label in SECRET_PATTERNS:
            for match in pattern.finditer(changed.patch):
                findings.append(Finding(agent="security_analysis", severity=Severity.CRITICAL,
                    category="possible_secret", title=label,
                    description="A credential-like value was matched in submitted change content.",
                    recommendation="Remove the value and rotate it if genuine; use a managed secret store.",
                    file=changed.path, line=_line(changed.patch, match.start()),
                    evidence=match.group(0)[:120], confidence=0.85))
        for pattern, label in RISKY_PATTERNS:
            for match in pattern.finditer(changed.patch):
                findings.append(Finding(agent="security_analysis", severity=Severity.HIGH,
                    category="risky_configuration", title=label,
                    description="A potentially unsafe pattern was found by a local heuristic.",
                    recommendation="Review the surrounding code and choose a safer configuration or API.",
                    file=changed.path, line=_line(changed.patch, match.start()),
                    evidence=match.group(0)[:120], confidence=0.8))
        if re.search(r"(?i)(auth|permission|role|token)", changed.path):
            findings.append(Finding(agent="code_analysis", severity=Severity.MEDIUM,
                category="security_sensitive_change", title="Security-sensitive file changed",
                description="The file path suggests authentication or authorisation logic changed.",
                recommendation="Add focused tests for permitted and denied access paths.",
                file=changed.path, evidence=f"Changed path: {changed.path}", confidence=0.65))
    return findings

def analyse_dependencies(manifest: str | None, ecosystem: str) -> list[Finding]:
    if not manifest or ecosystem.lower() not in {"python", "pip", "requirements.txt"}:
        return []
    findings = []
    for number, raw in enumerate(manifest.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        if not re.search(r"(==|~=|>=|<=|!=)", line):
            findings.append(Finding(agent="dependency_analysis", severity=Severity.LOW,
                category="unpinned_dependency", title="Dependency version is not constrained",
                description=f"'{line[:100]}' has no visible version constraint.",
                recommendation="Constrain versions and review updates through a lockfile.",
                file="requirements.txt", line=number, evidence=line[:120], confidence=0.95))
    return findings

def analyse_tests(request: ReleaseRequest) -> list[Finding]:
    summary = request.test_summary
    findings = []
    if summary.failed:
        findings.append(Finding(agent="test_intelligence", severity=Severity.HIGH,
            category="failing_tests", title="Test failures reported",
            description=f"{summary.failed} of {summary.total} reported tests failed.",
            recommendation="Resolve failures or document an explicit, reviewed waiver.",
            evidence=f"passed={summary.passed}, failed={summary.failed}, total={summary.total}"))
    if summary.total == 0:
        findings.append(Finding(agent="test_intelligence", severity=Severity.MEDIUM,
            category="missing_test_evidence", title="No test execution evidence supplied",
            description="No test execution results were attached to this release.",
            recommendation="Run relevant unit, integration and regression tests and attach results.",
            evidence="test_summary.total = 0"))
    if summary.coverage_percent is not None and summary.coverage_percent < 60:
        findings.append(Finding(agent="test_intelligence", severity=Severity.MEDIUM,
            category="low_coverage", title="Reported test coverage is below 60%",
            description=f"Reported coverage is {summary.coverage_percent:.1f}%.",
            recommendation="Add tests for changed modules and review coverage exclusions.",
            evidence=f"coverage_percent={summary.coverage_percent}"))
    return findings
