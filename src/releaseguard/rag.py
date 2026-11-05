"""Azure AI Search-backed policy retrieval for ReleaseGuard."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    title: str
    source: str
    section: str
    content: str
    content_hash: str


@dataclass(frozen=True)
class RetrievedPolicy:
    chunk_id: str
    title: str
    source: str
    section: str
    content: str
    score: float | None = None

    @property
    def citation(self) -> str:
        return f"{self.source}#{self.section}" if self.section else self.source


def chunk_markdown(text: str, *, source: str, max_chars: int = 1800,
                   overlap_chars: int = 180) -> list[PolicyChunk]:
    """Split Markdown on headings and paragraph boundaries with stable IDs."""
    if max_chars < 300 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Invalid chunk size or overlap")
    title = Path(source).stem.replace("-", " ").replace("_", " ").title()
    section = "Overview"
    chunks: list[PolicyChunk] = []
    buffer = ""

    def emit(value: str, current_section: str) -> None:
        content = value.strip()
        if not content:
            return
        digest = hashlib.sha256(
            f"{source}\0{current_section}\0{content}".encode("utf-8")
        ).hexdigest()
        chunks.append(PolicyChunk(
            chunk_id=digest, title=title, source=source,
            section=current_section, content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ))

    def append_piece(piece: str, current_section: str) -> None:
        nonlocal buffer
        piece = piece.strip()
        if not piece:
            return
        if len(piece) > max_chars:
            if buffer:
                emit(buffer, current_section)
                buffer = ""
            start = 0
            while start < len(piece):
                end = min(start + max_chars, len(piece))
                emit(piece[start:end], current_section)
                if end == len(piece):
                    break
                start = max(start + 1, end - overlap_chars)
            return
        if buffer and len(buffer) + len(piece) + 2 > max_chars:
            emit(buffer, current_section)
            tail = buffer[-overlap_chars:] if overlap_chars else ""
            buffer = f"{tail}" + chr(10) * 2 + f"{piece}"
        else:
            buffer = f"{buffer}" + chr(10) * 2 + f"{piece}"

    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            emit(buffer, section)
            buffer = ""
            section = heading.group(1).strip()
        else:
            append_piece(line, section)
    emit(buffer, section)
    return chunks


def load_policy_documents(directory: str | Path) -> list[PolicyChunk]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Policy directory does not exist: {root}")
    documents: list[PolicyChunk] = []
    for path in sorted(root.rglob("*.md")):
        if path.is_symlink():
            continue
        documents.extend(chunk_markdown(
            path.read_text(encoding="utf-8"),
            source=path.relative_to(root).as_posix(),
        ))
    if not documents:
        raise ValueError(f"No Markdown policy documents found in {root}")
    return documents


class AzureAISearchKnowledgeBase:
    """Vector retrieval using Azure AI Search and Azure OpenAI embeddings."""

    def __init__(self, *, endpoint: str, api_key: str, index_name: str,
                 embedding_deployment: str, openai_endpoint: str,
                 openai_api_key: str, api_version: str = "2024-10-21",
                 dimensions: int = 1536, search_client: Any | None = None,
                 index_client: Any | None = None,
                 embedding_client: Any | None = None,
                 vector_query_factory: Any | None = None) -> None:
        if not all([endpoint, api_key, index_name, embedding_deployment,
                    openai_endpoint, openai_api_key]):
            raise ValueError("Azure AI Search and Azure OpenAI settings are required")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", index_name):
            raise ValueError("Index name must be lowercase letters, digits and hyphens")
        self.index_name = index_name
        self.embedding_deployment = embedding_deployment
        self.dimensions = dimensions

        if search_client is None or index_client is None:
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents import SearchClient
                from azure.search.documents.indexes import SearchIndexClient
            except ImportError as exc:
                raise RuntimeError(
                    "Install RAG dependencies with: pip install -e '.[azure-rag]'"
                ) from exc
            credential = AzureKeyCredential(api_key)
            search_client = search_client or SearchClient(
                endpoint=endpoint, index_name=index_name, credential=credential
            )
            index_client = index_client or SearchIndexClient(
                endpoint=endpoint, credential=credential
            )
        if embedding_client is None:
            try:
                from openai import AzureOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "Install RAG dependencies with: pip install -e '.[azure-rag]'"
                ) from exc
            embedding_client = AzureOpenAI(
                azure_endpoint=openai_endpoint, api_key=openai_api_key,
                api_version=api_version,
            )
        self.search_client = search_client
        self.index_client = index_client
        self.embedding_client = embedding_client
        self.vector_query_factory = vector_query_factory

    @classmethod
    def from_environment(cls) -> "AzureAISearchKnowledgeBase":
        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise RuntimeError(f"RAG is enabled but {name} is not configured")
            return value
        return cls(
            endpoint=required("AZURE_SEARCH_ENDPOINT"),
            api_key=required("AZURE_SEARCH_API_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "releaseguard-policies"),
            embedding_deployment=required("AZURE_OPENAI_EMBEDDING_MODEL"),
            openai_endpoint=required("AZURE_OPENAI_ENDPOINT"),
            openai_api_key=required("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            dimensions=int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "1536")),
        )

    def ensure_index(self) -> None:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.search.documents.indexes.models import (
            HnswAlgorithmConfiguration, SearchField, SearchFieldDataType,
            SearchIndex, SearchableField, SimpleField, VectorSearch,
            VectorSearchProfile,
        )
        try:
            self.index_client.get_index(self.index_name)
            return
        except ResourceNotFoundError:
            pass
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="source", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="section", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="content_hash", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True, vector_search_dimensions=self.dimensions,
                vector_search_profile_name="releaseguard-vector-profile",
            ),
        ]
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="releaseguard-hnsw")],
            profiles=[VectorSearchProfile(
                name="releaseguard-vector-profile",
                algorithm_configuration_name="releaseguard-hnsw",
            )],
        )
        self.index_client.create_or_update_index(SearchIndex(
            name=self.index_name, fields=fields, vector_search=vector_search
        ))

    def _embed(self, text: str) -> list[float]:
        response = self.embedding_client.embeddings.create(
            model=self.embedding_deployment, input=text
        )
        vector = response.data[0].embedding
        if len(vector) != self.dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}"
            )
        return vector

    def ingest(self, chunks: Iterable[PolicyChunk]) -> int:
        self.ensure_index()
        documents = []
        for chunk in chunks:
            documents.append({
                "id": chunk.chunk_id, "title": chunk.title,
                "source": chunk.source, "section": chunk.section,
                "content": chunk.content, "content_hash": chunk.content_hash,
                "content_vector": self._embed(chunk.content),
            })
        if not documents:
            return 0
        results = self.search_client.upload_documents(documents=documents)
        failures = [item for item in results if not item.succeeded]
        if failures:
            raise RuntimeError(f"Azure AI Search rejected {len(failures)} policy chunks")
        return len(documents)

    def retrieve(self, query: str, *, top: int = 5) -> list[RetrievedPolicy]:
        if not query.strip():
            return []
        if top < 1 or top > 10:
            raise ValueError("top must be between 1 and 10")
        vector = self._embed(query[:6000])
        factory = self.vector_query_factory
        if factory is None:
            from azure.search.documents.models import VectorizedQuery
            factory = VectorizedQuery
        vector_query = factory(
            vector=vector, k_nearest_neighbors=top, fields="content_vector"
        )
        results = self.search_client.search(
            search_text=None, vector_queries=[vector_query],
            select=["id", "title", "source", "section", "content"], top=top,
        )
        return [RetrievedPolicy(
            chunk_id=str(item["id"]), title=str(item["title"]),
            source=str(item["source"]), section=str(item["section"]),
            content=str(item["content"]), score=item.get("@search.score"),
        ) for item in results]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index ReleaseGuard policy Markdown into Azure AI Search"
    )
    parser.add_argument("--source-dir", default="knowledge/policies")
    args = parser.parse_args()
    knowledge_base = AzureAISearchKnowledgeBase.from_environment()
    count = knowledge_base.ingest(load_policy_documents(args.source_dir))
    print(f"Indexed {count} policy chunks into '{knowledge_base.index_name}'")


if __name__ == "__main__":
    main()
