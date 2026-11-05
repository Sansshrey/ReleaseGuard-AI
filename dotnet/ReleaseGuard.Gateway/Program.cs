using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Azure;
using Azure.Data.Tables;
using Azure.Messaging.ServiceBus;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHttpClient("releaseguard-python", client =>
{
    var backend = builder.Configuration["ReleaseGuardBackendUrl"] ?? "http://127.0.0.1:8000";
    client.BaseAddress = new Uri(backend.TrimEnd('/') + "/");
    client.Timeout = TimeSpan.FromSeconds(90);
});

var app = builder.Build();

app.Use(async (context, next) =>
{
    if (context.Request.Path.Equals("/health", StringComparison.OrdinalIgnoreCase))
    {
        await next();
        return;
    }

    var expected = app.Configuration["GatewayApiKey"];
    var supplied = context.Request.Headers["X-API-Key"].ToString();
    if (string.IsNullOrWhiteSpace(expected) || !ApiKeyMatches(expected, supplied))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = "A valid X-API-Key header is required." });
        return;
    }

    await next();
});

app.MapGet("/health", () => Results.Ok(new { status = "ok", service = "releaseguard-dotnet-gateway" }));

app.MapPost("/api/releases", async (JsonElement body, IHttpClientFactory clients, HttpContext context) =>
    await ForwardAsync(clients, HttpMethod.Post, "api/releases", body, app.Configuration["ReleaseGuardBackendApiKey"], context.RequestAborted));

app.MapGet("/api/releases/{releaseId}/report", async (string releaseId, IHttpClientFactory clients, HttpContext context) =>
    await ForwardAsync(clients, HttpMethod.Get, $"api/releases/{Uri.EscapeDataString(releaseId)}/report", null, app.Configuration["ReleaseGuardBackendApiKey"], context.RequestAborted));

app.MapPost("/api/releases/{releaseId}/approve", async (string releaseId, JsonElement body, IHttpClientFactory clients, HttpContext context) =>
    await ForwardAsync(clients, HttpMethod.Post, $"api/releases/{Uri.EscapeDataString(releaseId)}/approve", body, app.Configuration["ReleaseGuardBackendApiKey"], context.RequestAborted));

app.MapPost("/api/releases/{releaseId}/reject", async (string releaseId, JsonElement body, IHttpClientFactory clients, HttpContext context) =>
    await ForwardAsync(clients, HttpMethod.Post, $"api/releases/{Uri.EscapeDataString(releaseId)}/reject", body, app.Configuration["ReleaseGuardBackendApiKey"], context.RequestAborted));

app.MapPost("/api/jobs", async (JsonElement body, HttpContext context) =>
{
    if (!IsReleaseRequest(body))
        return Results.BadRequest(new { error = "Body must contain repository, title and a non-empty changed_files array." });

    var jobId = Guid.NewGuid().ToString("N");
    var connection = app.Configuration["ServiceBusConnection"];
    if (string.IsNullOrWhiteSpace(connection))
        return Results.Problem("ServiceBusConnection is not configured.", statusCode: 503);

    var queueName = app.Configuration["ReleaseGuardQueue"] ?? "releaseguard-analysis";
    var table = CreateJobTable(app.Configuration);
    await table.CreateIfNotExistsAsync(context.RequestAborted);

    var entity = new TableEntity("analysis", jobId)
    {
        ["status"] = "queued",
        ["createdAtUtc"] = DateTimeOffset.UtcNow.ToString("O"),
        ["updatedAtUtc"] = DateTimeOffset.UtcNow.ToString("O")
    };
    await table.AddEntityAsync(entity, context.RequestAborted);

    await using var client = new ServiceBusClient(connection);
    await using var sender = client.CreateSender(queueName);
    var payload = JsonSerializer.Serialize(new { jobId, releaseRequest = body });
    await sender.SendMessageAsync(new ServiceBusMessage(payload)
    {
        MessageId = jobId,
        ContentType = "application/json"
    }, context.RequestAborted);

    return Results.Accepted($"/api/jobs/{jobId}", new { jobId, status = "queued" });
});

app.MapGet("/api/jobs/{jobId}", async (string jobId, HttpContext context) =>
{
    if (!Guid.TryParseExact(jobId, "N", out _))
        return Results.NotFound();

    var table = CreateJobTable(app.Configuration);
    await table.CreateIfNotExistsAsync(context.RequestAborted);
    var result = await table.GetEntityIfExistsAsync<TableEntity>("analysis", jobId, cancellationToken: context.RequestAborted);
    if (!result.HasValue)
        return Results.NotFound();

    var row = result.Value;
    return Results.Ok(new
    {
        jobId,
        status = row.GetString("status"),
        releaseId = row.GetString("releaseId"),
        error = row.GetString("error"),
        createdAtUtc = row.GetString("createdAtUtc"),
        updatedAtUtc = row.GetString("updatedAtUtc")
    });
});

app.Run();

static bool ApiKeyMatches(string expected, string supplied)
{
    var expectedBytes = Encoding.UTF8.GetBytes(expected);
    var suppliedBytes = Encoding.UTF8.GetBytes(supplied);
    return expectedBytes.Length == suppliedBytes.Length &&
           CryptographicOperations.FixedTimeEquals(expectedBytes, suppliedBytes);
}

static bool IsReleaseRequest(JsonElement body) =>
    body.ValueKind == JsonValueKind.Object &&
    body.TryGetProperty("repository", out var repository) &&
    repository.ValueKind == JsonValueKind.String &&
    !string.IsNullOrWhiteSpace(repository.GetString()) &&
    body.TryGetProperty("title", out var title) &&
    title.ValueKind == JsonValueKind.String &&
    !string.IsNullOrWhiteSpace(title.GetString()) &&
    body.TryGetProperty("changed_files", out var files) &&
    files.ValueKind == JsonValueKind.Array && files.GetArrayLength() > 0;

static TableClient CreateJobTable(IConfiguration configuration)
{
    var storage = configuration["AzureWebJobsStorage"];
    if (string.IsNullOrWhiteSpace(storage))
        throw new InvalidOperationException("AzureWebJobsStorage is required for durable job status.");
    return new TableServiceClient(storage).GetTableClient("ReleaseGuardJobs");
}

static async Task<IResult> ForwardAsync(
    IHttpClientFactory clients, HttpMethod method, string path, JsonElement? body,
    string? backendApiKey, CancellationToken cancellationToken)
{
    using var request = new HttpRequestMessage(method, path);
    if (body.HasValue)
        request.Content = JsonContent.Create(body.Value);
    if (!string.IsNullOrWhiteSpace(backendApiKey))
        request.Headers.Add("X-API-Key", backendApiKey);

    using var response = await clients.CreateClient("releaseguard-python")
        .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
    var content = await response.Content.ReadAsStringAsync(cancellationToken);
    return Results.Content(content, response.Content.Headers.ContentType?.ToString() ?? "application/json",
        statusCode: (int)response.StatusCode);
}
