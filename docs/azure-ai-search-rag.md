# Retrieval-augmented generation with Azure AI Search

ReleaseGuard retrieves version-controlled security, dependency and release-readiness
policy passages and supplies them as advisory context to its four Azure OpenAI
specialist agents.

## Implemented

- Markdown policy ingestion with heading-aware chunking and overlap.
- Stable SHA-256 chunk IDs and content hashes for repeatable indexing.
- Azure OpenAI embeddings and Azure AI Search vector retrieval.
- Citation metadata carried into AI findings through policy reference IDs.
- Validation rejects policy IDs that were not returned by the retriever for that
  specialist's current review.
- Release-code evidence is still independently validated against submitted
  change content. Deterministic risk scoring remains authoritative.

The starter corpus in `knowledge/policies/` is an engineering baseline, not a
complete or legally binding security standard. Review and version policy files
before organisational use.

## Install and configure

```bash
pip install -e ".[azure-rag]"
```

Configure:

```dotenv
RELEASEGUARD_AI_PROVIDER=azure_openai
RELEASEGUARD_RAG_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_MODEL=YOUR-CHAT-DEPLOYMENT
AZURE_OPENAI_EMBEDDING_MODEL=YOUR-EMBEDDING-DEPLOYMENT
AZURE_OPENAI_EMBEDDING_DIMENSIONS=1536
AZURE_SEARCH_ENDPOINT=https://YOUR-SERVICE.search.windows.net
AZURE_SEARCH_API_KEY=...
AZURE_SEARCH_INDEX=releaseguard-policies
```

The embedding deployment must output the configured vector dimension. The
default is 1536, suitable for a text-embedding-3-small deployment using its
default dimensions. If the deployment is configured with another output size,
set `AZURE_OPENAI_EMBEDDING_DIMENSIONS` to match exactly. The chat deployment
is not used for vectorization.

## Index the policy corpus

From the repository root:

```bash
python -m releaseguard.rag --source-dir knowledge/policies
```

The command creates the vector index if it does not exist and uploads the
Markdown chunks. Re-running it upserts the same stable document IDs. The
identity used for indexing needs permission to create indexes and upload
documents. Runtime retrieval needs search-read permission. This prototype uses
API keys; prefer Microsoft Entra ID and managed identity before production.

## Runtime flow

1. Each hosted specialist creates a short query from its specialty and
   sanitised pull-request evidence.
2. Azure OpenAI creates a query embedding.
3. Azure AI Search performs nearest-neighbour vector retrieval.
4. The specialist receives the top policy passages with source and section IDs.
5. Model findings may include policy citation IDs. The application rejects
   citations not present in that specialist's retrieved results.
6. Each finding must still cite exact release evidence. Policy citations
   support a recommendation; they do not replace code evidence.

See Microsoft's [Azure AI Search vector search quickstart](https://learn.microsoft.com/en-us/azure/search/search-get-started-vector)
and [Python SDK documentation](https://learn.microsoft.com/en-us/python/api/overview/azure/search-documents-readme?view=azure-python).

## Limits and security

- This version uses vector nearest-neighbour retrieval, not hybrid search or
  semantic reranking.
- The corpus is curated Markdown, not automatic crawling of arbitrary URLs.
- Do not ingest confidential policies unless the Azure resource, access model
  and data residency have been approved.
- Retrieved documents are reference context, not trusted instructions.
- Citation validation proves a chunk was retrieved; it does not prove the policy
  is correct or the model interpreted it correctly.
- Search and embedding calls require Azure resources and incur service costs.
