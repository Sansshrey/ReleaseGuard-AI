import json

import pytest

from releaseguard.llm_agents import AzureOpenAISpecialistAgent, redact_untrusted_text
from releaseguard.models import ReleaseRequest


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.prompt = None

    async def run(self, prompt):
        self.prompt = prompt
        return type("Response", (), {"text": self.response})()


def request():
    return ReleaseRequest(
        repository="demo/payments",
        title="Review callback",
        changed_files=[{
            "path": "src/client.py",
            "patch": "diff --git a/src/client.py b/src/client.py\n"
                     "@@ -1,1 +1,2 @@\n requests.get(url, verify=False)\n"
                     "+requests.get(url, verify=False)",
        }],
    )


def test_redacts_common_secret_patterns():
    result = redact_untrusted_text('api_key="super-secret-value-123" ghp_123456789012345678901234')
    assert "super-secret-value-123" not in result
    assert "ghp_123456789012345678901234" not in result
    assert "[REDACTED_SECRET]" in result


def test_agent_accepts_only_evidence_present_in_input():
    source = request()
    evidence = "requests.get(url, verify=False)"
    response = json.dumps({"findings": [{
        "severity": "high",
        "category": "tls",
        "title": "TLS verification disabled",
        "description": "TLS certificate checks are disabled.",
        "recommendation": "Enable certificate verification.",
        "file": "src/client.py",
        "line": 2,
        "evidence": evidence,
        "confidence": 0.9,
    }]})
    agent = AzureOpenAISpecialistAgent(
        name="azure_security_review",
        finding_agent="security_analysis",
        specialty="security",
        instructions="review",
        agent=FakeAgent(response),
    )
    findings = agent.run(source)
    assert len(findings) == 1
    assert findings[0].agent == "security_analysis"
    assert findings[0].source == "azure_openai_agent_framework"


def test_agent_rejects_fabricated_evidence():
    agent = AzureOpenAISpecialistAgent(
        name="azure_security_review",
        finding_agent="security_analysis",
        specialty="security",
        instructions="review",
        agent=FakeAgent(json.dumps({"findings": [{
            "severity": "critical", "category": "x", "title": "x",
            "description": "x", "recommendation": "x",
            "file": "src/client.py", "evidence": "made up evidence",
        }]})),
    )
    with pytest.raises(ValueError, match="evidence not present"):
        agent.run(request())


def test_agent_rejects_paths_outside_change_set():
    agent = AzureOpenAISpecialistAgent(
        name="azure_security_review",
        finding_agent="security_analysis",
        specialty="security",
        instructions="review",
        agent=FakeAgent(json.dumps({"findings": [{
            "severity": "high", "category": "x", "title": "x",
            "description": "x", "recommendation": "x",
            "file": "secrets.env", "evidence": "requests.get(url, verify=False)",
        }]})),
    )
    with pytest.raises(ValueError, match="outside"):
        agent.run(request())



def test_agent_includes_retrieved_policy_and_validates_policy_citations():
    from types import SimpleNamespace

    source = request()
    policy = SimpleNamespace(
        chunk_id="policy-chunk-1", source="security.md", section="TLS",
        title="Security baseline", content="TLS verification must remain enabled.",
    )
    class KnowledgeBase:
        def retrieve(self, query, top=5):
            assert "security" in query
            assert top == 5
            return [policy]

    response = json.dumps({"findings": [{
        "severity": "high", "category": "tls", "title": "TLS verification disabled",
        "description": "Certificate validation is disabled.",
        "recommendation": "Enable certificate validation.",
        "file": "src/client.py", "line": 2,
        "evidence": "requests.get(url, verify=False)",
        "policy_references": ["policy-chunk-1"],
    }]})
    fake = FakeAgent(response)
    agent = AzureOpenAISpecialistAgent(
        name="azure_security_review", finding_agent="security_analysis",
        specialty="security", instructions="review", agent=fake,
        knowledge_base=KnowledgeBase(),
    )
    findings = agent.run(source)
    assert findings[0].policy_references == ["policy-chunk-1"]
    assert findings[0].policy_citations[0].source == "security.md"
    assert findings[0].policy_citations[0].section == "TLS"
    assert findings[0].source == "azure_openai_agent_framework_rag"
    assert "TLS verification must remain enabled" in fake.prompt


def test_agent_rejects_policy_citation_not_returned_by_retriever():
    from types import SimpleNamespace

    class KnowledgeBase:
        def retrieve(self, query, top=5):
            return [SimpleNamespace(
                chunk_id="allowed-id", source="security.md", section="TLS",
                title="Security", content="Use TLS verification.",
            )]

    response = json.dumps({"findings": [{
        "severity": "high", "category": "tls", "title": "x",
        "description": "x", "recommendation": "x",
        "file": "src/client.py", "evidence": "requests.get(url, verify=False)",
        "policy_references": ["invented-id"],
    }]})
    agent = AzureOpenAISpecialistAgent(
        name="azure_security_review", finding_agent="security_analysis",
        specialty="security", instructions="review", agent=FakeAgent(response),
        knowledge_base=KnowledgeBase(),
    )
    with pytest.raises(ValueError, match="policy chunk"):
        agent.run(request())
