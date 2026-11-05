import asyncio
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
