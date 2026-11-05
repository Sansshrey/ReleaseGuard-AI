# ReleaseGuard Azure infrastructure

This directory is a parameterized Bicep baseline for the cloud architecture.

It provisions Azure Container Registry, Container Apps + Log Analytics, an internal Python FastAPI service, an external ASP.NET Core gateway, Service Bus, Storage, Azure AI Search, and Azure OpenAI.

## Deployment

1. Create a resource group.
2. Build the Python image and publish it to the generated ACR.
3. Publish the .NET gateway and build its image.
4. Copy `infra/parameters.example.json` to an untracked parameters file and replace both API keys with strong random values.
5. Run `az deployment group create --resource-group <rg> --template-file infra/main.bicep --parameters @<your-parameters>.json`.

The template does not create Azure OpenAI model deployments or the Search index because deployment names, quotas and index schemas are subscription/region-specific.

## Security boundary

The public surface is the .NET gateway. The Python service has internal Container Apps ingress. The current application uses API keys as a starter boundary; production should move to Microsoft Entra ID, managed identity, Key Vault references and role-based authorization.

The SQLite database remains on the container filesystem in this baseline and is not durable across replacement. Production persistence should move to Azure SQL or another managed store.

Do not commit populated parameter files or secrets.