# ReleaseGuard AI dashboard

React + Vite frontend for the ReleaseGuard assessment API.

## Run

    cd frontend
    npm install
    npm run dev

Set VITE_API_BASE_URL when the Python API is not running at http://127.0.0.1:8000. If the API is unavailable, the dashboard displays demo data so the UI can still be reviewed.

For protected deployments, VITE_API_KEY may be supplied at build time, but long-lived privileged credentials must not be embedded in a public browser bundle. Production should use an authenticated gateway and short-lived user tokens.

## Implemented

- Release risk summary and deterministic score ring.
- Severity counts and evidence-backed findings.
- Risk dimension breakdown.
- Deployment checklist and rollback plan.
- Human approve/reject controls wired to the existing API.
- Live report lookup by release ID.
- Responsive desktop/tablet/mobile layout.
