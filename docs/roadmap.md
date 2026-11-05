# Roadmap

## Implemented
- [x] Local FastAPI API and validated release request
- [x] Deterministic code/security, dependency-manifest and test-evidence checks
- [x] Transparent weighted risk score and human approval workflow
- [x] SQLite persistence and hash-chained audit events (local prototype)
- [x] Read-only GitHub pull-request ingestion and GitHub Actions test evidence
- [x] Optional Semgrep and OSV-Scanner adapters
- [x] Local specialist-agent orchestration
- [x] Opt-in Microsoft Agent Framework + Azure OpenAI specialist-agent integration
- [x] Azure-agent evidence validation, secret redaction and mock-based tests
- [x] Azure AI Search vector retrieval, curated Markdown policy corpus and validated policy citation references

## Planned
- [x] C# ASP.NET Core gateway with API-key protection and Python service proxy
- [x] Azure Functions isolated worker with Service Bus queue processing and Azure Table job status
- [x] React + Vite release governance dashboard
- [x] Azure deployment infrastructure baseline (Bicep, ACR, Container Apps, Service Bus, Storage, Search, Azure OpenAI)
- [x] 100-case labelled synthetic benchmark dataset and offline evaluator for F1, classification, citation validity, latency and cost (measured report still pending)
- [ ] Production authentication, authorisation, monitoring, threat modelling and deployment hardening

Mark roadmap items complete only after implementation and tests exist. Do not publish performance or accuracy claims until measured.
