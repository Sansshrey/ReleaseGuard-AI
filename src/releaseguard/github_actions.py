"""Read-only GitHub Actions evidence retrieval and bounded report parsing."""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath
from typing import Any

import httpx

from .github_client import GITHUB_API, GitHubClient, GitHubIntegrationError
from .models import TestSummary

MAX_ARTIFACT_BYTES = 15 * 1024 * 1024
MAX_XML_BYTES = 5 * 1024 * 1024
ARTIFACT_NAME = "releaseguard-test-evidence"


class GitHubActionsClient(GitHubClient):
    """Fetch workflow metadata and one explicitly named evidence artifact."""

    def get_workflow_run(self, owner: str, name: str, run_id: int) -> dict[str, Any]:
        repository = self.validate_repository(owner, name)
        if run_id < 1:
            raise GitHubIntegrationError("Workflow run ID must be positive.")
        return self._get(f"{GITHUB_API}/repos/{repository}/actions/runs/{run_id}")

    def get_workflow_artifacts(self, owner: str, name: str, run_id: int) -> list[dict[str, Any]]:
        repository = self.validate_repository(owner, name)
        payload = self._get(
            f"{GITHUB_API}/repos/{repository}/actions/runs/{run_id}/artifacts",
            {"per_page": 100},
        )
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        if not isinstance(artifacts, list):
            raise GitHubIntegrationError("GitHub returned an invalid workflow-artifacts response.")
        return artifacts

    def download_artifact(self, owner: str, name: str, artifact_id: int) -> bytes:
        repository = self.validate_repository(owner, name)
        if artifact_id < 1:
            raise GitHubIntegrationError("Artifact ID must be positive.")
        url = f"{GITHUB_API}/repos/{repository}/actions/artifacts/{artifact_id}/zip"
        try:
            chunks: list[bytes] = []
            total = 0
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                with client.stream("GET", url, headers=self._headers()) as response:
                    if response.status_code in (401, 403):
                        raise GitHubIntegrationError("GitHub denied artifact access; check Actions read permission.")
                    if response.status_code == 404:
                        raise GitHubIntegrationError("Workflow artifact was not found or has expired.")
                    if response.status_code >= 400:
                        raise GitHubIntegrationError(
                            f"GitHub artifact download returned HTTP {response.status_code}."
                        )
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_ARTIFACT_BYTES:
                            raise GitHubIntegrationError("Workflow evidence artifact exceeds the 15 MB limit.")
                        chunks.append(chunk)
        except GitHubIntegrationError:
            raise
        except httpx.TimeoutException as exc:
            raise GitHubIntegrationError("GitHub artifact download timed out.") from exc
        except httpx.HTTPError as exc:
            raise GitHubIntegrationError("Could not download the GitHub Actions artifact.") from exc
        return b"".join(chunks)

def _safe_xml(data: bytes) -> ET.Element:
    if len(data) > MAX_XML_BYTES:
        raise ValueError("XML report exceeds the 5 MB limit.")
    # ElementTree does not fetch external entities; reject DTD/entity declarations too.
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("XML report contains a prohibited DTD/entity declaration.")
    return ET.fromstring(data)


def parse_evidence_artifact(archive_bytes: bytes, run_id: int) -> TestSummary:
    """Parse JUnit XML and Cobertura coverage.xml without extracting ZIP paths."""
    if len(archive_bytes) > MAX_ARTIFACT_BYTES:
        raise ValueError("Workflow evidence artifact exceeds the 15 MB limit.")

    total = failures = errors = skipped = 0
    coverage_percent: float | None = None
    per_file: dict[str, float] = {}
    found_junit = found_coverage = False

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Workflow evidence artifact is not a valid ZIP archive.") from exc

    with archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        if len(entries) > 100:
            raise ValueError("Workflow evidence artifact contains too many files.")
        total_uncompressed = sum(item.file_size for item in entries)
        if total_uncompressed > 20 * 1024 * 1024:
            raise ValueError("Workflow evidence artifact expands beyond the 20 MB limit.")
        total_uncompressed = sum(item.file_size for item in entries)
        if total_uncompressed > 20 * 1024 * 1024:
            raise ValueError("Workflow evidence artifact expands beyond the 20 MB limit.")
        for item in entries:
            name = PurePosixPath(item.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Workflow evidence artifact contains an unsafe file path.")
            if item.file_size > MAX_XML_BYTES or item.compress_size > MAX_XML_BYTES:
                continue
            leaf = name.name.lower()
            if not (leaf.endswith(".xml") and (
                "junit" in leaf or "test-results" in leaf or leaf == "coverage.xml"
            )):
                continue
            data = archive.read(item)
            try:
                root = _safe_xml(data)
            except (ET.ParseError, ValueError):
                continue

            if leaf == "coverage.xml" or root.tag.rsplit("}", 1)[-1] == "coverage":
                found_coverage = True
                rate = root.attrib.get("line-rate")
                try:
                    coverage_percent = round(float(rate) * 100, 2)
                except (TypeError, ValueError):
                    coverage_percent = None
                for node in root.iter():
                    if node.tag.rsplit("}", 1)[-1] not in {"class", "file"}:
                        continue
                    path = node.attrib.get("filename") or node.attrib.get("name")
                    raw_rate = node.attrib.get("line-rate")
                    if not path or raw_rate is None:
                        continue
                    try:
                        value = round(float(raw_rate) * 100, 2)
                    except ValueError:
                        continue
                    normalized = str(PurePosixPath(path))
                    per_file[normalized] = value
                continue

            if root.tag.rsplit("}", 1)[-1] not in {"testsuite", "testsuites"}:
                continue
            found_junit = True
            suites = [root] if root.tag.rsplit("}", 1)[-1] == "testsuite" else [
                node for node in root.iter()
                if node.tag.rsplit("}", 1)[-1] == "testsuite"
            ]
            for suite in suites:
                try:
                    total += int(suite.attrib.get("tests", "0"))
                    failures += int(suite.attrib.get("failures", "0"))
                    errors += int(suite.attrib.get("errors", "0"))
                    skipped += int(suite.attrib.get("skipped", "0"))
                except ValueError:
                    raise ValueError("JUnit report contains invalid test counts.")

    if not found_junit and not found_coverage:
        raise ValueError("Artifact contains neither a readable JUnit report nor coverage.xml.")

    return TestSummary(
        total=total,
        passed=max(0, total - failures - errors - skipped),
        failed=failures + errors,
        coverage_percent=coverage_percent,
        coverage_files=per_file,
        evidence_source="github_actions",
        workflow_run_id=run_id,
        skipped=skipped,
    )



def load_pull_request_test_evidence(
    client: GitHubActionsClient,
    owner: str,
    name: str,
    pull_number: int,
    run_id: int,
    expected_head_sha: str | None,
) -> TestSummary:
    """Require a completed workflow run for this exact PR head before parsing evidence."""
    run = client.get_workflow_run(owner, name, run_id)
    if run.get("status") != "completed":
        raise GitHubIntegrationError("Workflow run has not completed; test evidence is not final.")
    if run.get("event") != "pull_request":
        raise GitHubIntegrationError("Only pull_request workflow runs can supply PR test evidence.")
    if expected_head_sha and run.get("head_sha") != expected_head_sha:
        raise GitHubIntegrationError("Workflow run does not match the pull request's current head commit.")

    linked_prs = run.get("pull_requests") or []
    if not any(
        isinstance(item, dict) and item.get("number") == pull_number
        for item in linked_prs
    ):
        raise GitHubIntegrationError("Workflow run is not associated with the requested pull request.")

    artifacts = client.get_workflow_artifacts(owner, name, run_id)
    artifact = next(
        (
            item for item in artifacts
            if item.get("name") == ARTIFACT_NAME and not item.get("expired", False)
        ),
        None,
    )
    if artifact is None:
        raise GitHubIntegrationError(
            f"Workflow run has no unexpired '{ARTIFACT_NAME}' artifact. Check the CI upload step."
        )
    try:
        artifact_size = int(artifact.get("size_in_bytes", 0))
        if artifact_size > MAX_ARTIFACT_BYTES:
            raise GitHubIntegrationError("Workflow evidence artifact exceeds the 15 MB limit.")
        artifact_id = int(artifact.get("id"))
    except (TypeError, ValueError) as exc:
        raise GitHubIntegrationError("GitHub returned an invalid evidence artifact ID.") from exc
    archive = client.download_artifact(owner, name, artifact_id)
    try:
        return parse_evidence_artifact(archive, run_id)
    except ValueError as exc:
        raise GitHubIntegrationError(f"Could not parse workflow test evidence: {exc}") from exc
