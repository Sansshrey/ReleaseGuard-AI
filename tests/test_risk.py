from releaseguard.models import Finding, ReleaseRequest, Severity
from releaseguard.risk import calculate_risk

def sample_request():
    return ReleaseRequest(repository="demo/service", title="Test release",
        changed_files=[{"path": "app.py", "patch": "print('ok')"}],
        api_compatibility_score=0,
        test_summary={"total": 10, "passed": 10, "failed": 0, "coverage_percent": 85})

def test_clean_release_scores_zero():
    result = calculate_risk(sample_request(), [])
    assert result.total == 0
    assert result.level == "low"

def test_critical_security_finding_increases_security_dimension():
    finding = Finding(agent="security_analysis", severity=Severity.CRITICAL,
        category="possible_secret", title="Possible secret", description="test",
        recommendation="Rotate it", evidence="redacted credential pattern")
    result = calculate_risk(sample_request(), [finding])
    assert result.security == 90
    assert result.total > 0

def test_risk_is_bounded():
    result = calculate_risk(sample_request(), [])
    assert 0 <= result.total <= 100
