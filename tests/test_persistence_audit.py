from releaseguard.models import ReleaseRequest
from releaseguard.repository import SQLiteReleaseRepository
from releaseguard.service import ReleaseService


def make_request():
    return ReleaseRequest(
        repository="example/payments", title="Add payment callback",
        changed_files=[{"path": "src/payments.py", "patch": "def callback(): pass"}],
    )


def test_release_survives_service_restart(tmp_path):
    db = tmp_path / "releaseguard.db"
    created = ReleaseService(repository=SQLiteReleaseRepository(db)).analyse(make_request())
    loaded = ReleaseService(repository=SQLiteReleaseRepository(db)).get(created.release_id)
    assert loaded.request.repository == "example/payments"
    assert loaded.decision.value == "review_required"


def test_decision_is_persisted_and_audited(tmp_path):
    db = tmp_path / "releaseguard.db"
    service = ReleaseService(repository=SQLiteReleaseRepository(db))
    created = service.analyse(make_request())
    service.decide(created.release_id, True, "Reviewed and approved")
    restarted = ReleaseService(repository=SQLiteReleaseRepository(db))
    assert restarted.get(created.release_id).decision.value == "approved"
    events = restarted.list_audit_events(created.release_id)
    assert [event["event_type"] for event in events] == [
        "release_created", "release_decision_changed"
    ]
    assert events[1]["details"]["previous_decision"] == "review_required"
    assert events[1]["details"]["decision"] == "approved"
    assert restarted.verify_audit_chain()["valid"] is True


def test_audit_events_reject_update_and_delete(tmp_path):
    import sqlite3
    db = tmp_path / "releaseguard.db"
    service = ReleaseService(repository=SQLiteReleaseRepository(db))
    created = service.analyse(make_request())
    connection = sqlite3.connect(db)
    try:
        for statement in (
            "UPDATE audit_events SET event_type = 'tampered' WHERE release_id = ?",
            "DELETE FROM audit_events WHERE release_id = ?",
        ):
            try:
                connection.execute(statement, (created.release_id,))
                assert False, "audit mutation should have been rejected"
            except sqlite3.IntegrityError as exc:
                assert "append-only" in str(exc)
    finally:
        connection.close()


def test_audit_verification_detects_out_of_band_tampering(tmp_path):
    import sqlite3
    db = tmp_path / "releaseguard.db"
    service = ReleaseService(repository=SQLiteReleaseRepository(db))
    service.analyse(make_request())
    connection = sqlite3.connect(db)
    try:
        connection.execute("DROP TRIGGER audit_events_no_update")
        connection.execute("UPDATE audit_events SET event_hash = 'bad' WHERE sequence = 1")
        connection.commit()
    finally:
        connection.close()
    result = service.verify_audit_chain()
    assert result["valid"] is False
    assert result["failed_sequence"] == 1
