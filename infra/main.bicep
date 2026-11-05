targetScope = 'resourceGroup'

param location string = resourceGroup().location
@minLength(3)
@maxLength(18)
param namePrefix string = 'releaseguard'
param imageTag string = 'latest'
@secure() param gatewayApiKey string
@secure() param backendApiKey string
@secure() param githubToken string = ''
@secure() param azureOpenAiApiKey string = ''
@secure() param searchApiKey string = ''
param enableAzureAi bool = false
param enableRag bool = false

var suffix = uniqueString(resourceGroup().id, namePrefix)
var safePrefix = toLower(replace(namePrefix, '-', ''))
var acrName = '\${safePrefix}\${take(suffix, 8)}'
var storageName = '\${take(safePrefix, 14)}\${take(suffix, 10)}'
var serviceBusName = '\${safePrefix}-bus-\${take(suffix, 6)}'
var searchName = '\${safePrefix}-search-\${take(suffix, 6)}'
var openAiName = '\${safePrefix}-aoai-\${take(suffix, 6)}'
var envName = '\${safePrefix}-cae-\${take(suffix, 6)}'
var logName = '\${safePrefix}-logs-\${take(suffix, 6)}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: logName
  location: location
  properties: { retentionInDays: 30, sku: { name: 'PerGB2018' } }
}
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false, publicNetworkAccess: 'Enabled' }
}
resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusName
  location: location
  sku: { name: 'Standard' }
  properties: { publicNetworkAccess: 'Enabled' }
}
resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBus
  name: 'releaseguard-analysis'
  properties: { maxDeliveryCount: 10, lockDuration: 'PT5M', deadLetteringOnMessageExpiration: true }
}
resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false, publicNetworkAccess: 'Enabled' }
}
resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: location
  sku: { name: 'basic' }
  properties: { replicaCount: 1, partitionCount: 1, hostingMode: 'default', publicNetworkAccess: 'enabled' }
}
resource openAi 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: openAiName
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: { customSubDomainName: openAiName, publicNetworkAccess: 'Enabled' }
}
resource containerEnv 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}
resource pythonApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: '\${safePrefix}-api-\${take(suffix, 6)}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: { external: false, targetPort: 8000, transport: 'http' }
      secrets: [
        { name: 'backend-api-key'; value: backendApiKey }
        { name: 'github-token'; value: githubToken }
        { name: 'azure-openai-key'; value: azureOpenAiApiKey }
        { name: 'search-key'; value: searchApiKey }
      ]
      registries: [{ server: acr.properties.loginServer, identity: 'system' }]
    }
    template: {
      containers: [{
        name: 'releaseguard-api'
        image: '\${acr.properties.loginServer}/releaseguard-api:\${imageTag}'
        resources: { cpu: 1, memory: '2Gi' }
        env: [
          { name: 'RELEASEGUARD_API_KEY'; secretRef: 'backend-api-key' }
          { name: 'GITHUB_TOKEN'; secretRef: 'github-token' }
          { name: 'RELEASEGUARD_AI_PROVIDER'; value: enableAzureAi ? 'azure_openai' : 'local' }
          { name: 'AZURE_OPENAI_ENDPOINT'; value: 'https://\${openAi.name}.openai.azure.com/' }
          { name: 'AZURE_OPENAI_API_KEY'; secretRef: 'azure-openai-key' }
          { name: 'RELEASEGUARD_RAG_ENABLED'; value: enableRag ? 'true' : 'false' }
          { name: 'AZURE_SEARCH_ENDPOINT'; value: 'https://\${search.name}.search.windows.net' }
          { name: 'AZURE_SEARCH_API_KEY'; secretRef: 'search-key' }
          { name: 'RELEASEGUARD_DB_PATH'; value: '/data/releaseguard.db' }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}
resource gatewayApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: '\${safePrefix}-gateway-\${take(suffix, 6)}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: { external: true, targetPort: 8080, transport: 'http' }
      secrets: [
        { name: 'gateway-api-key'; value: gatewayApiKey }
        { name: 'backend-api-key'; value: backendApiKey }
        { name: 'storage-connection'; value: storage.listKeys().keys[0].value }
        { name: 'servicebus-connection'; value: serviceBus.listKeys().authorizationRuleKeys[0].primaryConnectionString }
      ]
      registries: [{ server: acr.properties.loginServer, identity: 'system' }]
    }
    template: {
      containers: [{
        name: 'releaseguard-gateway'
        image: '\${acr.properties.loginServer}/releaseguard-gateway:\${imageTag}'
        resources: { cpu: 0.5, memory: '1Gi' }
        env: [
          { name: 'GatewayApiKey'; secretRef: 'gateway-api-key' }
          { name: 'ReleaseGuardBackendApiKey'; secretRef: 'backend-api-key' }
          { name: 'ReleaseGuardBackendUrl'; value: 'http://\${pythonApp.name}' }
          { name: 'AzureWebJobsStorage'; secretRef: 'storage-connection' }
          { name: 'ServiceBusConnection'; secretRef: 'servicebus-connection' }
          { name: 'ReleaseGuardQueue'; value: 'releaseguard-analysis' }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}
resource acrPullPython 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, pythonApp.id, 'acrpull')
  scope: acr
  properties: {
    principalId: pythonApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}
resource acrPullGateway 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, gatewayApp.id, 'acrpull')
  scope: acr
  properties: {
    principalId: gatewayApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}
output acrLoginServer string = acr.properties.loginServer
output gatewayUrl string = 'https://\${gatewayApp.properties.configuration.ingress.fqdn}'
output pythonInternalUrl string = 'http://\${pythonApp.name}'
output serviceBusNamespace string = serviceBus.name
output searchEndpoint string = 'https://\${search.name}.search.windows.net'
output azureOpenAiEndpoint string = 'https://\${openAi.name}.openai.azure.com/'