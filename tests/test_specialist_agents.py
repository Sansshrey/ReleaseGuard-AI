from releaseguard.agents import CodeAnalysisAgent, SecurityAnalysisAgent
from releaseguard.models import ReleaseRequest


def _request(patch: str):
    return ReleaseRequest(
        repository="demo/service",
        title="Update service",
        changed_files=[{"path": "src/service.py", "patch": patch}],
    )


def test_code_agent_detects_bare_except_on_added_lines():
    findings = CodeAnalysisAgent().run(_request("@@ -1,0 +1,2 @@\n+try:\n+    work()\n+except:\n+    pass"))
    assert len(findings) == 1
    assert findings[0].category == "code_quality"
    assert findings[0].line == 4


def test_security_agent_detects_dynamic_execution_on_added_lines():
    findings = SecurityAnalysisAgent().run(_request("@@ -1,0 +1 @@\n+result = eval(user_input)"))
    assert len(findings) == 1
    assert findings[0].category == "risky_configuration"
    assert findings[0].file == "src/service.py"


def test_security_agent_ignores_removed_lines():
    findings = SecurityAnalysisAgent().run(_request("@@ -1 +0,0 @@\n-eval(user_input)"))
    assert findings == []


def test_agents_are_independent():
    request = _request("@@ -1,0 +1 @@\n+result = eval(user_input)")
    assert CodeAnalysisAgent().run(request) == []
    assert len(SecurityAnalysisAgent().run(request)) == 1
