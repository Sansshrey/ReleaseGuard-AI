from fastapi.testclient import TestClient
from releaseguard import main
from releaseguard.models import ReleaseRequest

client = TestClient(main.app)


class FakeClient:
    pass


def test_github_pull_request_route_uses_ingestion_and_assessment(monkeypatch):
    request = ReleaseRequest(
        repository="acme/payments",
        pull_request=7,
        title="PR from GitHub",
        changed_files=[{"path": "app.py", "patch": "verify = False"}],
    )
    monkeypatch.setattr(main, "GitHubClient", FakeClient)
    monkeypatch.setattr(main, "build_release_request", lambda client, owner, name, number: request)
    response = client.post("/api/github/acme/payments/pulls/7/analyse")
    assert response.status_code == 201
    assert response.json()["request"]["repository"] == "acme/payments"
    assert response.json()["request"]["pull_request"] == 7


def test_github_integration_error_is_returned_as_gateway_error(monkeypatch):
    def fail(*args, **kwargs):
        raise main.GitHubIntegrationError("Pull request was not found.")
    monkeypatch.setattr(main, "GitHubClient", FakeClient)
    monkeypatch.setattr(main, "build_release_request", fail)
    response = client.post("/api/github/acme/payments/pulls/999/analyse")
    assert response.status_code == 502
    assert response.json()["detail"] == "Pull request was not found."
