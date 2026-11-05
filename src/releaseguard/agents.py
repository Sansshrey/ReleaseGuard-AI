"""Bounded specialist agents used by the local release assessment workflow.

These agents deliberately use deterministic local analyzers. They do not execute
submitted code, call external models, or make deployment decisions.
"""
from __future__ import annotations

from typing import Protocol

from .analyzers import analyse_changes, analyse_dependencies, analyse_tests
from .models import Finding, ReleaseRequest


class SpecialistAgent(Protocol):
    """Common contract for a specialist that inspects one release request."""

    name: str

    def run(self, request: ReleaseRequest) -> list[Finding]:
        """Return evidence-backed findings for the supplied release."""


class CodeAnalysisAgent:
    name = "code_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return [item for item in analyse_changes(request) if item.agent == self.name]


class SecurityAnalysisAgent:
    name = "security_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return [item for item in analyse_changes(request) if item.agent == self.name]


class DependencyAnalysisAgent:
    name = "dependency_analysis"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return analyse_dependencies(request.dependency_manifest, request.dependency_ecosystem)


class TestIntelligenceAgent:
    name = "test_intelligence"

    def run(self, request: ReleaseRequest) -> list[Finding]:
        return analyse_tests(request)
