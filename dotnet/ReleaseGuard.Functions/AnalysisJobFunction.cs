using System.Net.Http.Json;
using System.Text.Json;
using Azure;
using Azure.Data.Tables;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

namespace ReleaseGuard.Functions;

public sealed class AnalysisJobFunction(
    IHttpClientFactory clients,
    TableClient jobs,
    ILogger<AnalysisJobFunction> logger)
{
    [Function(nameof(AnalyseReleaseJob))]
    public async Task AnalyseReleaseJob(
        [ServiceBusTrigger("%ReleaseGuardQueue%", Connection = "ServiceBusConnection")] string message,
        CancellationToken cancellationToken)
    {
        var job = JsonSerializer.Deserialize<AnalysisJob>(message, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        if (job is null || !Guid.TryParseExact(job.JobId, "N", out _))
            throw new InvalidOperationException("Queue message is not a valid ReleaseGuard analysis job.");

        await jobs.CreateIfNotExistsAsync(cancellationToken);
        await SetStatus(job.JobId, "processing", null, null, cancellationToken);
        logger.LogInformation("Processing ReleaseGuard job {JobId}", job.JobId);

        using var request = new HttpRequestMessage(HttpMethod.Post, "api/releases")
        {
            Content = JsonContent.Create(job.ReleaseRequest)
        };
        var backendKey = Environment.GetEnvironmentVariable("ReleaseGuardBackendApiKey");
        if (!string.IsNullOrWhiteSpace(backendKey))
            request.Headers.Add("X-API-Key", backendKey);

        using var response = await clients.CreateClient("releaseguard-python")
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var detail = await response.Content.ReadAsStringAsync(cancellationToken);
            await SetStatus(job.JobId, "failed", null,
                $"Python analysis API returned {(int)response.StatusCode}: {detail[..Math.Min(detail.Length, 1000)]}",
                cancellationToken);

            if ((int)response.StatusCode >= 500 || response.StatusCode == System.Net.HttpStatusCode.RequestTimeout)
                throw new HttpRequestException($"Transient analysis backend failure: {(int)response.StatusCode}");
            return;
        }

        using var result = await JsonDocument.ParseAsync(
            await response.Content.ReadAsStreamAsync(cancellationToken), cancellationToken: cancellationToken);
        var releaseId = result.RootElement.TryGetProperty("release_id", out var id) ? id.GetString() : null;
        if (string.IsNullOrWhiteSpace(releaseId))
            throw new InvalidOperationException("Analysis API response did not contain release_id.");

        await SetStatus(job.JobId, "completed", releaseId, null, cancellationToken);
        logger.LogInformation("Completed ReleaseGuard job {JobId} as release {ReleaseId}", job.JobId, releaseId);
    }

    private async Task SetStatus(
        string jobId, string status, string? releaseId, string? error, CancellationToken cancellationToken)
    {
        var entity = new TableEntity("analysis", jobId)
        {
            ["status"] = status,
            ["updatedAtUtc"] = DateTimeOffset.UtcNow.ToString("O")
        };
        if (releaseId is not null) entity["releaseId"] = releaseId;
        if (error is not null) entity["error"] = error;
        await jobs.UpsertEntityAsync(entity, TableUpdateMode.Merge, cancellationToken);
    }

    private sealed record AnalysisJob(string JobId, JsonElement ReleaseRequest);
}
