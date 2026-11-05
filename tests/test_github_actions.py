import io
import zipfile

import pytest

from releaseguard.github_actions import parse_evidence_artifact


def _zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_parse_junit_and_cobertura_reports():
    artifact = _zip({
        "junit.xml": (
            '<testsuites><testsuite tests="5" failures="1" errors="1" skipped="1">'
            '</testsuite></testsuites>'
        ),
        "coverage.xml": (
            '<coverage line-rate="0.72"><packages><package><classes>'
            '<class filename="src/payments.py" line-rate="0.45"/>'
            '</classes></package></packages></coverage>'
        ),
    })
    summary = parse_evidence_artifact(artifact, 123)
    assert summary.total == 5
    assert summary.passed == 2
    assert summary.failed == 2
    assert summary.skipped == 1
    assert summary.coverage_percent == 72.0
    assert summary.coverage_files["src/payments.py"] == 45.0
    assert summary.workflow_run_id == 123
    assert summary.evidence_source == "github_actions"


def test_reject_invalid_zip():
    with pytest.raises(ValueError, match="valid ZIP"):
        parse_evidence_artifact(b"not a zip", 1)


def test_reject_zip_path_traversal():
    artifact = _zip({"../junit.xml": '<testsuite tests="0"/>'})
    with pytest.raises(ValueError, match="unsafe file path"):
        parse_evidence_artifact(artifact, 1)


def test_reject_xml_doctype():
    artifact = _zip({"junit.xml": '<!DOCTYPE x [<!ENTITY e "boom">]><testsuite tests="1"/>'})
    with pytest.raises(ValueError, match="DTD/entity"):
        parse_evidence_artifact(artifact, 1)


def test_requires_at_least_one_recognized_report():
    artifact = _zip({"notes.txt": "nothing"})
    with pytest.raises(ValueError, match="neither a readable"):
        parse_evidence_artifact(artifact, 1)



def test_artifact_expansion_limit_is_enforced():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("junit.xml", '<testsuite tests="0"/>')
        archive.writestr("coverage.xml", '<coverage line-rate="0.8"/>')
        archive.writestr("other.xml", "x" * (20 * 1024 * 1024))
    with pytest.raises(ValueError, match="expands beyond"):
        parse_evidence_artifact(buffer.getvalue(), 7)
