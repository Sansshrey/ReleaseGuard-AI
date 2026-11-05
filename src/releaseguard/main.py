"""FastAPI entry point for the ReleaseGuard AI local MVP."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .github_client import GitHubClient, GitHubIntegrationError
from .github_ingestion import build_release_request
from .github_actions import GitHubActionsClient, load_pull_request_test_evidence
from .models import ReleaseRecord, ReleaseRequest
from .service import ReleaseNotFoundError, ReleaseService

app = FastAPI(title="ReleaseGuard AI",
    description="Local-first release risk analysis and human approval workflow.",
    version="0.1.0")
service = ReleaseService()

class DecisionRequest(BaseModel):
    note: str = Field(min_length=3, max_length=1000)

@app.get("/health")
def health():
    return {"status": "ok", "service": "releaseguard-ai"}

@app.post("/api/releases", response_model=ReleaseRecord, status_code=201)
def create_release(request: ReleaseRequest):
    return service.analyse(request)

@app.post("/api/github/{owner}/{name}/pulls/{number}/analyse", response_model=ReleaseRecord, status_code=201)
def analyse_github_pull_request(owner: str, name: str, number: int):
    """Fetch an open PR using read-only GitHub API access and analyse its diff."""
    try:
        request = build_release_request(GitHubClient(), owner, name, number)
        return service.analyse(request)
    except GitHubIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/github/{owner}/{name}/pulls/{number}/runs/{run_id}/analyse", response_model=ReleaseRecord, status_code=201)
def analyse_github_pull_request_with_ci(owner: str, name: str, number: int, run_id: int):
    """Analyse an open PR using its matching completed GitHub Actions test artifact."""
    try:
        request = build_release_request(GitHubClient(), owner, name, number)
        request.test_summary = load_pull_request_test_evidence(
            GitHubActionsClient(), owner, name, number, run_id,
            request.metadata.get("head_sha"),
        )
        request.metadata["workflow_run_id"] = run_id
        request.metadata["test_evidence_source"] = "github_actions"
        return service.analyse(request)
    except GitHubIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.get("/api/releases/{release_id}", response_model=ReleaseRecord)
def get_release(release_id: str):
    try:
        return service.get(release_id)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")

@app.get("/api/releases/{release_id}/audit")
def get_release_audit(release_id: str):
    try:
        return {"release_id": release_id, "events": service.list_audit_events(release_id)}
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")


@app.get("/api/audit/integrity")
def verify_audit_integrity():
    return service.verify_audit_chain()


@app.get("/api/releases/{release_id}/findings")
def get_findings(release_id: str):
    try:
        return service.list_findings(release_id)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")

@app.get("/api/releases/{release_id}/report")
def get_report(release_id: str):
    try:
        record = service.get(release_id)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")
    return {"release_id": record.release_id, "repository": record.request.repository,
        "title": record.request.title, "risk": record.risk, "decision": record.decision,
        "findings": record.findings, "deployment_checklist": record.deployment_checklist,
        "rollback_plan": record.rollback_plan, "human_approval_note": record.approval_note}

@app.post("/api/releases/{release_id}/approve", response_model=ReleaseRecord)
def approve_release(release_id: str, body: DecisionRequest):
    try:
        return service.decide(release_id, True, body.note)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")

@app.post("/api/releases/{release_id}/reject", response_model=ReleaseRecord)
def reject_release(release_id: str, body: DecisionRequest):
    try:
        return service.decide(release_id, False, body.note)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")
