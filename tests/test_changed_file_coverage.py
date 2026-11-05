from releaseguard.analyzers import analyse_tests
from releaseguard.models import ReleaseRequest


def test_changed_file_coverage_finding_uses_per_file_evidence():
    request = ReleaseRequest(
        repository="demo/api",
        title="Change payment logic",
        changed_files=[{"path": "src/payments.py", "patch": "+def charge(): pass"}],
        test_summary={
            "total": 10,
            "passed": 10,
            "coverage_percent": 80,
            "coverage_files": {"src/payments.py": 42.5},
            "evidence_source": "github_actions",
            "workflow_run_id": 123,
        },
    )
    findings = analyse_tests(request)
    assert len(findings) == 1
    assert findings[0].category == "changed_file_low_coverage"
    assert findings[0].file == "src/payments.py"
    assert findings[0].source == "github_actions"


def test_changed_file_missing_from_coverage_report_is_flagged():
    request = ReleaseRequest(
        repository="demo/api",
        title="Change payment logic",
        changed_files=[{"path": "src/payments.py", "patch": "+def charge(): pass"}],
        test_summary={
            "total": 10,
            "passed": 10,
            "coverage_percent": 80,
            "coverage_files": {"src/other.py": 95},
        },
    )
    findings = analyse_tests(request)
    assert any(item.category == "changed_file_missing_coverage" for item in findings)
