"""Validated request and response models."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"RG-{uuid4().hex[:8].upper()}")
    agent: str
    severity: Severity
    category: str
    title: str
    description: str
    recommendation: str
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    evidence: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "local_heuristic"\n    policy_references: list[str] = Field(default_factory=list, max_length=10)

class ChangedFile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    patch: str = Field(default="", max_length=100_000)

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        path = value.replace("\\", "/")
        if path.startswith("/") or ".." in path.split("/"):
            raise ValueError("File path must be relative and cannot traverse directories")
        return path

class TestSummary(BaseModel):
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    coverage_percent: float | None = Field(default=None, ge=0, le=100)
    coverage_files: dict[str, float] = Field(default_factory=dict)
    evidence_source: str | None = None
    workflow_run_id: int | None = Field(default=None, ge=1)
    skipped: int = Field(default=0, ge=0)

class ReleaseRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=300)
    pull_request: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=500)
    base_branch: str = "main"
    head_branch: str = "feature"
    changed_files: list[ChangedFile] = Field(min_length=1, max_length=500)
    dependency_manifest: str | None = Field(default=None, max_length=100_000)
    dependency_ecosystem: str = "python"
    test_summary: TestSummary = Field(default_factory=TestSummary)
    api_compatibility_score: float = Field(default=50, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

class RiskBreakdown(BaseModel):
    security: float
    code_quality: float
    dependency: float
    testing: float
    api_compatibility: float
    total: int
    level: str
    weights: dict[str, float]

class ReleaseDecision(StrEnum):
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"

class AgentExecution(BaseModel):
    agent: str
    status: str
    duration_ms: float = Field(ge=0)
    finding_count: int = Field(ge=0)

class ReleaseRecord(BaseModel):
    release_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utc_now)
    request: ReleaseRequest
    findings: list[Finding]
    agent_executions: list[AgentExecution] = Field(default_factory=list)
    risk: RiskBreakdown
    decision: ReleaseDecision = ReleaseDecision.REVIEW_REQUIRED
    deployment_checklist: list[str]
    rollback_plan: list[str]
    approval_note: str | None = None
