"""Transparent, deterministic risk scoring."""
from .models import Finding, ReleaseRequest, RiskBreakdown, Severity

WEIGHTS = {"security": 0.30, "code_quality": 0.25, "dependency": 0.20, "testing": 0.15, "api_compatibility": 0.10}
SEVERITY_POINTS = {Severity.INFO: 5, Severity.LOW: 15, Severity.MEDIUM: 35, Severity.HIGH: 65, Severity.CRITICAL: 90}

def _dimension_score(findings: list[Finding], agents: set[str]) -> float:
    residual = 1.0
    for finding in findings:
        if finding.agent in agents:
            residual *= 1.0 - SEVERITY_POINTS[finding.severity] / 100.0
    return round((1.0 - residual) * 100.0, 2)

def calculate_risk(request: ReleaseRequest, findings: list[Finding]) -> RiskBreakdown:
    security = _dimension_score(findings, {"security_analysis"})
    code = _dimension_score(findings, {"code_analysis"})
    dependency = _dimension_score(findings, {"dependency_analysis"})
    testing = _dimension_score(findings, {"test_intelligence"})
    api = float(request.api_compatibility_score)
    total = round(WEIGHTS["security"] * security + WEIGHTS["code_quality"] * code
        + WEIGHTS["dependency"] * dependency + WEIGHTS["testing"] * testing
        + WEIGHTS["api_compatibility"] * api)
    level = "high" if total >= 70 else "medium" if total >= 40 else "low"
    return RiskBreakdown(security=security, code_quality=code, dependency=dependency,
        testing=testing, api_compatibility=api, total=total, level=level, weights=WEIGHTS.copy())
