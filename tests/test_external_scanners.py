import json
from pathlib import Path

from releaseguard.external_scanners import scan_osv, scan_semgrep
from releaseguard.models import ReleaseRequest


def _request():
    return ReleaseRequest(
        repository="demo/service",
        title="Update service",
        changed_files=[{
            "path": "src/service.py",
            "patch": "@@ -1,0 +1,1 @@\n+result = eval(user_input)",
        }],
        dependency_manifest="requests==2.19.0\n",
    )


def test_semgrep_is_optional_when_binary_is_missing(monkeypatch):
    monkeypatch.setattr("releaseguard.external_scanners.shutil.which", lambda _: None)
    assert scan_semgrep(_request()) == []


def test_osv_is_optional_when_binary_is_missing(monkeypatch):
    monkeypatch.setattr("releaseguard.external_scanners.shutil.which", lambda _: None)
    assert scan_osv(_request()) == []


def test_semgrep_results_are_mapped_to_original_file(monkeypatch):
    monkeypatch.setattr("releaseguard.external_scanners.shutil.which", lambda _: "/usr/bin/semgrep")
    def fake_run(command, **kwargs):
        target = Path(command[-1]) / "changed_0.py"
        payload = {
            "results": [{
                "check_id": "python.lang.security.audit.eval-detected",
                "path": str(target),
                "start": {"line": 1},
                "extra": {
                    "severity": "ERROR",
                    "message": "Avoid eval with untrusted input",
                    "lines": "result = eval(user_input)",
                },
            }]
        }
        class Completed:
            stdout = json.dumps(payload)
            returncode = 0
        return Completed()
    monkeypatch.setattr("releaseguard.external_scanners.subprocess.run", fake_run)
    findings = scan_semgrep(_request())
    assert len(findings) == 1
    assert findings[0].file == "src/service.py"
    assert findings[0].source == "semgrep"
    assert findings[0].severity.value == "high"


def test_osv_results_are_mapped_to_dependency_findings(monkeypatch):
    monkeypatch.setattr("releaseguard.external_scanners.shutil.which", lambda _: "/usr/bin/osv-scanner")
    def fake_run(command, **kwargs):
        payload = {
            "results": [{
                "packages": [{
                    "package": {"name": "requests", "version": "2.19.0"},
                    "vulnerabilities": [{
                        "id": "GHSA-test-1234",
                        "summary": "Example advisory",
                        "severity": [{"type": "CVSS_V3", "score": "8.1"}],
                    }],
                }],
            }],
        }
        class Completed:
            stdout = json.dumps(payload)
            returncode = 1
        return Completed()
    monkeypatch.setattr("releaseguard.external_scanners.subprocess.run", fake_run)
    findings = scan_osv(_request())
    assert len(findings) == 1
    assert findings[0].category == "known_vulnerability"
    assert findings[0].source == "osv_scanner"
    assert findings[0].severity.value == "high"
    assert "requests@2.19.0" in findings[0].evidence


def test_semgrep_timeout_does_not_crash_assessment(monkeypatch):
    import subprocess
    monkeypatch.setattr("releaseguard.external_scanners.shutil.which", lambda _: "/usr/bin/semgrep")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("semgrep", 45)
    monkeypatch.setattr("releaseguard.external_scanners.subprocess.run", timeout)
    assert scan_semgrep(_request()) == []
