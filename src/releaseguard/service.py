"""Release assessment workflow backed by persistent SQLite storage."""
from .models import ReleaseDecision, ReleaseRecord, ReleaseRequest
from .orchestrator import ReleaseSupervisor
from .repository import SQLiteReleaseRepository
from .risk import calculate_risk


class ReleaseNotFoundError(KeyError):
    """Raised when a release ID is unknown."""


class ReleaseService:
    def __init__(self, supervisor: ReleaseSupervisor | None = None,
                 repository: SQLiteReleaseRepository | None = None) -> None:
        self._repository = repository or SQLiteReleaseRepository()
        self._supervisor = supervisor or ReleaseSupervisor()

    def analyse(self, request: ReleaseRequest) -> ReleaseRecord:
        findings, executions = self._supervisor.analyse(request)
        record = ReleaseRecord(
            request=request, findings=findings, agent_executions=executions,
            risk=calculate_risk(request, findings),
            deployment_checklist=[
                "Confirm release owner and maintenance window.",
                "Verify CI is green and required reviewers have signed off.",
                "Confirm monitoring, alert thresholds and support coverage.",
                "Use a staged rollout or canary where supported.",
                "Verify health checks and critical user journeys.",
            ],
            rollback_plan=[
                "Pause rollout and notify the release owner.",
                "Revert to the last known-good artifact or deployment revision.",
                "Verify service health, data integrity and critical journeys.",
                "Record the incident, decision and follow-up actions.",
            ],
        )
        self._repository.save_new(record)
        return record

    def get(self, release_id: str) -> ReleaseRecord:
        record = self._repository.get(release_id)
        if record is None:
            raise ReleaseNotFoundError(release_id)
        return record

    def decide(self, release_id: str, approved: bool, note: str) -> ReleaseRecord:
        record = self.get(release_id)
        previous = record.decision.value
        record.decision = ReleaseDecision.APPROVED if approved else ReleaseDecision.REJECTED
        record.approval_note = note
        self._repository.update_decision(record, previous)
        return record

    def list_findings(self, release_id: str):
        return self.get(release_id).findings

    def list_audit_events(self, release_id: str):
        self.get(release_id)
        return self._repository.list_audit_events(release_id)

    def verify_audit_chain(self):
        return self._repository.verify_audit_chain()
