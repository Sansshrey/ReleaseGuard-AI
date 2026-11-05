# Persistence and audit trail

## SQLite persistence

Release records are stored in SQLite. Set `RELEASEGUARD_DB_PATH` to select the
database file; the default is `releaseguard.db` in the process working
directory. Parent directories are created automatically. SQLite WAL mode and
a 10-second busy timeout support concurrent local requests.

Existing in-memory records are not migrated. The new database starts empty.

## Audit events

Creating a release appends a `release_created` event. Each approve/reject
operation updates the release and appends a `release_decision_changed` event
in one transaction. Events include the release ID, timestamp, decision
details, previous hash and SHA-256 event hash.

Each event hash covers its canonical event data and the previous event hash.
SQLite triggers reject ordinary UPDATE and DELETE operations on the audit
table. The integrity endpoint recalculates the chain and reports the first
invalid sequence.

This is **tamper-evident, not tamper-proof**. A database administrator or
attacker with filesystem/database control can alter the database and triggers.
Production use needs authenticated actors, restricted database permissions,
external log replication, retention controls and managed database hosting.

## API

- `GET /api/releases/{release_id}/audit` returns that release's event history.
- `GET /api/audit/integrity` verifies the global event hash chain.

The API still has no authentication or authorization. Do not expose it publicly.
