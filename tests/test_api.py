from fastapi.testclient import TestClient
from releaseguard.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_create_report_and_approval():
    payload = {
        "repository": "example/payments",
        "title": "Add payment callback",
        "changed_files": [{"path": "src/auth.py", "patch": "requests.get(url, verify=False)"}],
        "test_summary": {"total": 0, "passed": 0, "failed": 0}
    }
    created = client.post("/api/releases", json=payload)
    assert created.status_code == 201
    release_id = created.json()["release_id"]
    report = client.get(f"/api/releases/{release_id}/report")
    assert report.status_code == 200
    assert report.json()["decision"] == "review_required"
    assert len(report.json()["findings"]) >= 2
    approved = client.post(f"/api/releases/{release_id}/approve", json={"note": "Reviewed by release owner"})
    assert approved.status_code == 200
    assert approved.json()["decision"] == "approved"

def test_invalid_traversal_path_is_rejected():
    payload = {"repository": "demo/repo", "title": "bad path",
        "changed_files": [{"path": "../secrets.txt", "patch": "x"}]}
    assert client.post("/api/releases", json=payload).status_code == 422

def test_missing_release_returns_404():
    assert client.get("/api/releases/not-a-real-id").status_code == 404
