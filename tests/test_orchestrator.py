from releaseguard.models import ReleaseRequest
from releaseguard.orchestrator import AgentExecutionError, ReleaseSupervisor


def _request():
    return ReleaseRequest(
        repository="demo/payments",
        title="Add payment endpoint",
        changed_files=[{"path": "src/auth.py", "patch": "requests.get(url, verify=False)"}],
        dependency_manifest="fastapi\nhttpx==0.27.0",
        test_summary={"total": 0},
    )


def test_supervisor_runs_all_specialists_and_returns_stable_execution_records():
    findings, executions = ReleaseSupervisor().analyse(_request())

    assert [item.agent for item in executions] == [
        "code_analysis", "security_analysis", "dependency_analysis", "test_intelligence"
    ]
    assert all(item.status == "completed" for item in executions)
    assert sum(item.finding_count for item in executions) == len(findings)
    assert any(item.category == "risky_configuration" for item in findings)
    assert any(item.category == "unpinned_dependency" for item in findings)
    assert any(item.category == "missing_test_evidence" for item in findings)


def test_supervisor_fails_assessment_when_a_specialist_fails():
    class BrokenAgent:
        name = "broken"

        def run(self, request):
            raise RuntimeError("scanner unavailable")

    try:
        ReleaseSupervisor(agents=[BrokenAgent()]).analyse(_request())
    except AgentExecutionError as exc:
        assert "broken" in str(exc)
    else:
        raise AssertionError("Expected specialist failure to abort assessment")
