# Security model

## Current MVP safeguards
- Submitted source text is analysed but never executed.
- Payloads and individual patch sizes are bounded.
- File paths must be relative and cannot contain parent-directory traversal segments.
- Findings include evidence snippets and are labelled as local heuristics.
- Approval endpoints record a decision only; they do not deploy or merge code.

## Required before production
1. Add authentication and role-based authorisation to all release and decision endpoints.
2. Persist append-only audit events for assessment and approval changes.
3. Verify GitHub webhook HMAC signatures and reject stale or replayed deliveries.
4. Use least-privilege, read-only GitHub credentials for ingestion.
5. Store credentials in a managed secret store; never log tokens or raw secret values.
6. Redact sensitive data from diffs, logs, prompts and reports.
7. Treat PR descriptions, comments, filenames and source code as untrusted input.
8. Never allow untrusted PR content to override system policy or agent tool permissions.
9. Isolate any future scanner execution with resource limits; do not run PR code.
10. Keep production deployment outside agent permissions and require human approval.

The local MVP has no authentication or durable storage and must not be exposed to the public internet.
