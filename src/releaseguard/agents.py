"""Bounded specialist agents used by the local release assessment workflow."""
from __future__ import annotations

from typing import Protocol

from .analyzers import (
    analyse_code_changes,
    analyse_dependencies,
    analyse_security_changes,
    analyse_tests,
)
from .external_scanners import scan_osv, scan_semgrep
from .models import Finding, ReleaseRequest


class SpecialistAgent(Protocol):
    """Common contract for a specialist that inspects one release request."""

    name: str

    def run(self, request: ReleaseRequest) -> list[Finding]:
        """Return evidence-backed findings for the supplied release."""


class CodeAnalysisAgent:
    name = "code_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return analyse_code_changes(request)


class SecurityAnalysisAgent:
    name = "security_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return analyse_security_changes(request) + scan_semgrep(request)


class DependencyAnalysisAgent:
    name = "dependency_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return (
            analyse_dependencies(request.dependency_manifest, request.dependency_ecosystem)
            + scan_osv(request)
        )


class TestIntelligenceAgent:
    name = "test_intelligence"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return analyse_tests(request)
