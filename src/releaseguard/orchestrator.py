"""Local supervisor for bounded, concurrent specialist-agent execution."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

from .agents import (
    CodeAnalysisAgent,
    DependencyAnalysisAgent,
    SecurityAnalysisAgent,
    SpecialistAgent,
    TestIntelligenceAgent,
)
from .models import AgentExecution, Finding, ReleaseRequest


class AgentExecutionError(RuntimeError):
    """Raised when a specialist fails; partial assessments are not persisted."""


class ReleaseSupervisor:
    """Dispatch specialists concurrently and return results in stable agent order."""

    def __init__(self, agents: list[SpecialistAgent] | None = None, max_workers: int = 4):
        self.agents = agents or [
            CodeAnalysisAgent(),
            SecurityAnalysisAgent(),
            DependencyAnalysisAgent(),
            TestIntelligenceAgent(),
        ]
        if not self.agents:
            raise ValueError("At least one specialist agent is required")
        names = [agent.name for agent in self.agents]
        if len(names) != len(set(names)):
            raise ValueError("Specialist agent names must be unique")
        self.max_workers = max(1, min(max_workers, len(self.agents)))

    def analyse(self, request: ReleaseRequest) -> tuple[list[Finding], list[AgentExecution]]:
        results: dict[str, tuple[list[Finding], float]] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._run_one, agent, request): agent.name
                for agent in self.agents
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    for pending in futures:
                        pending.cancel()
                    raise AgentExecutionError(
                        f"Specialist '{name}' failed; assessment was not completed"
                    ) from exc

        findings: list[Finding] = []
        executions: list[AgentExecution] = []
        for agent in self.agents:
            agent_findings, duration_ms = results[agent.name]
            findings.extend(agent_findings)
            executions.append(AgentExecution(
                agent=agent.name,
                status="completed",
                duration_ms=duration_ms,
                finding_count=len(agent_findings),
            ))
        return findings, executions

    @staticmethod
    def _run_one(agent: SpecialistAgent, request: ReleaseRequest) -> tuple[list[Finding], float]:
        started = perf_counter()
        findings = agent.run(request)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return findings, elapsed_ms


def build_supervisor_from_environment() -> ReleaseSupervisor:
    """Build local specialists and optionally add Microsoft Agent Framework agents."""
    import os

    agents: list[SpecialistAgent] = [
        CodeAnalysisAgent(),
        SecurityAnalysisAgent(),
        DependencyAnalysisAgent(),
        TestIntelligenceAgent(),
    ]
    provider = os.getenv("RELEASEGUARD_AI_PROVIDER", "local").strip().lower()
    if provider in {"", "local"}:
        return ReleaseSupervisor(agents=agents)
    if provider != "azure_openai":
        raise ValueError("RELEASEGUARD_AI_PROVIDER must be 'local' or 'azure_openai'")

    from .llm_agents import build_azure_openai_agents

    knowledge_base = None
    if os.getenv("RELEASEGUARD_RAG_ENABLED", "false").strip().lower() in {"1", "true", "yes"}:
        from .rag import AzureAISearchKnowledgeBase
        knowledge_base = AzureAISearchKnowledgeBase.from_environment()
    agents.extend(build_azure_openai_agents(knowledge_base=knowledge_base))
    return ReleaseSupervisor(agents=agents)
