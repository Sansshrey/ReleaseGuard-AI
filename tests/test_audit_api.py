from fastapi.testclient import TestClient

from releaseguard.main import app

client = TestClient(app)


def test_audit_endpoints_expose_creation_and_decision_events():
    payload = {
        "repository": "example/audit-api",
        "title": "Add audit endpoint test",
        "changed_files": [{"path": "src/audit.py", "patch": "def audit(): pass"}],
    }
    created = client.post("/api/releases", json=payload)
    assert created.status_code == 201
    release_id = created.json()["release_id"]

    audit = client.get(f"/api/releases/{release_id}/audit")
    assert audit.status_code == 200
    assert [item["event_type"] for item in audit.json()["events"]] == ["release_created"]

    approved = client.post(
        f"/api/releases/{release_id}/approve",
        json={"note": "Reviewed for audit endpoint test"},
    )
    assert approved.status_code == 200

    audit = client.get(f"/api/releases/{release_id}/audit")
    assert [item["event_type"] for item in audit.json()["events"]] == [
        "release_created", "release_decision_changed"
    ]
    integrity = client.get("/api/audit/integrity")
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
