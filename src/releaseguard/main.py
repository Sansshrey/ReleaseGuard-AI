"""FastAPI entry point for the ReleaseGuard AI local MVP."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .github_client import GitHubClient, GitHubIntegrationError
from .github_ingestion import build_release_request
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

@app.get("/api/releases/{release_id}", response_model=ReleaseRecord)
def get_release(release_id: str):
    try:
        return service.get(release_id)
    except ReleaseNotFoundError:
        raise HTTPException(status_code=404, detail="Release assessment not found")

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
