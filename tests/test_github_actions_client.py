from releaseguard.github_actions import (
    ARTIFACT_NAME,
    GitHubActionsClient,
    load_pull_request_test_evidence,
)
from releaseguard.github_client import GitHubIntegrationError


class FakeActionsClient(GitHubActionsClient):
    def __init__(self, run, artifacts, archive=b"zip"):
        super().__init__(token="fake")
        self.run = run
        self.artifacts = artifacts
        self.archive = archive

    def get_workflow_run(self, owner, name, run_id):
        return self.run

    def get_workflow_artifacts(self, owner, name, run_id):
        return self.artifacts

    def download_artifact(self, owner, name, artifact_id):
        return self.archive


def _run(**overrides):
    value = {
        "status": "completed",
        "event": "pull_request",
        "head_sha": "abc123",
        "pull_requests": [{"number": 7}],
    }
    value.update(overrides)
    return value


def test_requires_matching_completed_pull_request_run():
    client = FakeActionsClient(_run(), [{"id": 5, "name": ARTIFACT_NAME}])
    assert client is not None
    with __import__("pytest").raises(GitHubIntegrationError, match="not completed"):
        load_pull_request_test_evidence(
            FakeActionsClient(_run(status="in_progress"), []),
            "owner", "repo", 7, 99, "abc123",
        )


def test_rejects_stale_commit_run():
    with __import__("pytest").raises(GitHubIntegrationError, match="current head"):
        load_pull_request_test_evidence(
            FakeActionsClient(_run(head_sha="old"), []),
            "owner", "repo", 7, 99, "abc123",
        )


def test_requires_exact_named_artifact():
    with __import__("pytest").raises(GitHubIntegrationError, match="no unexpired"):
        load_pull_request_test_evidence(
            FakeActionsClient(_run(), [{"id": 1, "name": "other"}]),
            "owner", "repo", 7, 99, "abc123",
        )


def test_rejects_run_not_linked_to_pr():
    with __import__("pytest").raises(GitHubIntegrationError, match="not associated"):
        load_pull_request_test_evidence(
            FakeActionsClient(_run(pull_requests=[{"number": 8}]), []),
            "owner", "repo", 7, 99, "abc123",
        )
