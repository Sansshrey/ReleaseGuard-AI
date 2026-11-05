# Azure OpenAI specialist agents

ReleaseGuard supports an opt-in Azure OpenAI analysis mode implemented with
Microsoft Agent Framework (Python). The local deterministic specialists remain
enabled and run alongside four isolated model-backed reviewers.

## Install

```bash
pip install -e ".[azure-ai]"
```

## Configure

Copy the settings into your local environment (never commit credentials):

```dotenv
RELEASEGUARD_AI_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_MODEL=YOUR-CHAT-DEPLOYMENT-NAME
AZURE_OPENAI_API_VERSION=2024-10-21
```

`AZURE_OPENAI_MODEL` is the Azure deployment name, not necessarily the
underlying model family name. The deployment must support chat completions.
The Agent Framework integration uses its `Agent` abstraction and
`OpenAIChatClient` Azure endpoint configuration. See the
[Microsoft Agent Framework Python guide](https://github.com/microsoft/agent-framework/blob/main/python/README.md).

When `RELEASEGUARD_AI_PROVIDER` is unset or `local`, no Agent Framework
package or Azure credential is required. When set to `azure_openai`, startup
validates the required settings and creates four model-backed specialists.

## Safety and output validation

- Each model agent has no tools and receives only bounded JSON evidence.
- PR code, comments, filenames and test output are explicitly treated as
  untrusted data. Instructions inside them must be ignored.
- Common credential patterns and private-key blocks are redacted before
  transmission to the hosted model.
- Model output must be strict JSON. Findings are capped, validated against the
  Pydantic model, and must cite an exact substring from the supplied evidence.
- A finding cannot cite a file outside the submitted changed-file list.
- Model findings are advisory. They cannot approve releases, invoke tools,
  execute submitted code, or set the numeric risk score.
- The deterministic weighted risk engine remains authoritative.
- Hosted inference sends sanitised source snippets to the configured Azure
  resource. Enable this mode only when that data transfer is permitted by your
  organisation's policy.

If a model agent fails or returns invalid evidence, the assessment fails rather
than persisting a misleading partial AI assessment. The local-only mode remains
available without Azure credentials.
