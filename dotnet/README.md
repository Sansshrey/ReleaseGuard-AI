# .NET services

The .NET 10 solution adds a protected ASP.NET Core gateway and a Service Bus
triggered Azure Functions worker around the existing Python analysis service.

## Components

- **Gateway**: requires `GatewayApiKey` on every route except `/health`.
  It proxies synchronous analysis/report/decision calls to the Python API and
  accepts asynchronous jobs at `POST /api/jobs`.
- **Azure Functions worker**: consumes `releaseguard-analysis` messages,
  calls Python `POST /api/releases`, and updates durable job state.
- **Azure Table Storage**: stores queue job status under the
  `ReleaseGuardJobs` table. API callers poll `GET /api/jobs/{jobId}`.

## Configuration

Set these environment variables (never commit real values):

| Variable | Used by | Purpose |
|---|---|---|
| `GatewayApiKey` | Gateway | External API key for the gateway |
| `ReleaseGuardBackendUrl` | Gateway + Functions | Private Python API base URL |
| `ReleaseGuardBackendApiKey` | Gateway + Functions | Optional key forwarded to Python |
| `RELEASEGUARD_API_KEY` | Python | Enforces the forwarded `X-API-Key` |
| `ServiceBusConnection` | Gateway + Functions | Service Bus namespace connection |
| `ReleaseGuardQueue` | Gateway + Functions | Queue name (default in gateway: releaseguard-analysis) |
| `AzureWebJobsStorage` | Gateway + Functions | Storage account connection for durable job status and Functions host |

For local development, use Azurite for Tables and a real or emulator-compatible
Service Bus environment. The sample settings file is a template, not a complete
emulator configuration.

## Run

Terminal 1: start the Python API as documented in the root README.

Terminal 2:

```bash
export GatewayApiKey="local-dev-only-change-me"
export ReleaseGuardBackendUrl="http://127.0.0.1:8000"
export AzureWebJobsStorage="<storage-connection-string>"
export ServiceBusConnection="<service-bus-connection-string>"
dotnet run --project dotnet/ReleaseGuard.Gateway
```

Terminal 3: configure the same storage and Service Bus values plus
`ReleaseGuardBackendUrl`, then run:

```bash
dotnet run --project dotnet/ReleaseGuard.Functions
```

Submit a release synchronously through `POST /api/releases`, or enqueue it with
`POST /api/jobs`. The async endpoint returns HTTP 202 with a job ID. Poll
`GET /api/jobs/{jobId}` until its state is `completed` or `failed`; a completed
job includes the Python service's `releaseId`.

## Security and operational notes

- The gateway API key is a starter authentication boundary, not a full identity
  platform. Use Microsoft Entra ID, managed identities, Key Vault and role-based
  authorisation before production.
- Keep the Python API on a private network. Configure `RELEASEGUARD_API_KEY`
  and the same `ReleaseGuardBackendApiKey` in the .NET services.
- Use managed identity for Service Bus and Storage in production; this starter
  uses connection strings to keep local setup straightforward.
- Service Bus provides at-least-once delivery. The Python analysis endpoint
  creates a new release record per successful call, so a transient failure after
  the backend commits but before the worker records completion can produce a
  duplicate assessment on retry. Add an idempotency key to the Python service
  before treating this as a production workflow.
- Configure dead-letter monitoring, queue TTL, alerts, network restrictions,
  secret rotation and deployment slots before production.
