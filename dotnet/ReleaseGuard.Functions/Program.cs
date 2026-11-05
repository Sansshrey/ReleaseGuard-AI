using Azure.Data.Tables;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var host = new HostBuilder()
    .ConfigureFunctionsWorkerDefaults()
    .ConfigureServices(services =>
    {
        services.AddHttpClient("releaseguard-python", client =>
        {
            var backend = Environment.GetEnvironmentVariable("ReleaseGuardBackendUrl") ?? "http://127.0.0.1:8000";
            client.BaseAddress = new Uri(backend.TrimEnd('/') + "/");
            client.Timeout = TimeSpan.FromMinutes(3);
        });
        services.AddSingleton(_ =>
        {
            var storage = Environment.GetEnvironmentVariable("AzureWebJobsStorage")
                ?? throw new InvalidOperationException("AzureWebJobsStorage is required.");
            return new TableServiceClient(storage).GetTableClient("ReleaseGuardJobs");
        });
    })
    .Build();

host.Run();
