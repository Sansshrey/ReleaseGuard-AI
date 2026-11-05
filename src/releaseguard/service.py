"""Release assessment workflow and human decision handling."""
from .analyzers import analyse_changes, analyse_dependencies, analyse_tests
from .models import ReleaseRecord, ReleaseRequest
from .risk import calculate_risk

class ReleaseNotFoundError(KeyError):
    """Raised when a release ID is unknown."""

class ReleaseService:
    def __init__(self) -> None:
        self._records: dict[str, ReleaseRecord] = {}

    def analyse(self, request: ReleaseRequest) -> ReleaseRecord:
        findings = (analyse_changes(request)
            + analyse_dependencies(request.dependency_manifest, request.dependency_ecosystem)
            + analyse_tests(request))
        record = ReleaseRecord(request=request, findings=findings,
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
            ])
        self._records[record.release_id] = record
        return record

    def get(self, release_id: str) -> ReleaseRecord:
        try:
            return self._records[release_id]
        except KeyError as exc:
            raise ReleaseNotFoundError(release_id) from exc

    def decide(self, release_id: str, approved: bool, note: str) -> ReleaseRecord:
        record = self.get(release_id)
        record.decision = "approved" if approved else "rejected"
        record.approval_note = note
        return record

    def list_findings(self, release_id: str):
        return self.get(release_id).findings
