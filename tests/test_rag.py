import pytest

from releaseguard.rag import AzureAISearchKnowledgeBase, chunk_markdown, load_policy_documents


def test_markdown_chunking_tracks_heading_and_stable_ids():
    source = "# Security\n\nFirst paragraph.\n\n## TLS\n\nVerify certificates."
    chunks = chunk_markdown(source, source="security.md", max_chars=300)
    assert len(chunks) == 2
    assert chunks[0].section == "Security"
    assert chunks[1].section == "TLS"
    assert chunks[0].chunk_id == chunk_markdown(
        source, source="security.md", max_chars=300
    )[0].chunk_id


def test_chunking_splits_oversized_paragraphs():
    chunks = chunk_markdown("## Rule\n\n" + ("x" * 850), source="policy.md",
                            max_chars=300, overlap_chars=30)
    assert len(chunks) > 1
    assert all(len(item.content) <= 300 for item in chunks)


def test_chunking_rejects_invalid_sizes():
    with pytest.raises(ValueError):
        chunk_markdown("text", source="a.md", max_chars=200, overlap_chars=200)


def test_load_policy_documents_reads_markdown(tmp_path):
    (tmp_path / "policy.md").write_text(
        "# Policy\n\nUse least privilege.", encoding="utf-8"
    )
    chunks = load_policy_documents(tmp_path)
    assert chunks[0].source == "policy.md"
    assert "least privilege" in chunks[0].content


def test_load_policy_documents_rejects_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="No Markdown"):
        load_policy_documents(tmp_path)


def test_azure_knowledge_base_requires_complete_configuration():
    with pytest.raises(ValueError, match="settings are required"):
        AzureAISearchKnowledgeBase(
            endpoint="", api_key="", index_name="releaseguard-policies",
            embedding_deployment="", openai_endpoint="", openai_api_key="",
        )


def test_azure_knowledge_base_retrieval_uses_vector_search():
    class Embeddings:
        def create(self, **kwargs):
            assert kwargs["model"] == "embed-deployment"
            item = type("Item", (), {"embedding": [0.1, 0.2]})()
            return type("Response", (), {"data": [item]})()

    class Search:
        def search(self, **kwargs):
            assert kwargs["search_text"] is None
            assert kwargs["vector_queries"][0].fields == "content_vector"
            return [{
                "id": "abc", "title": "Security", "source": "security.md",
                "section": "TLS", "content": "Verify certificates.",
                "@search.score": 0.91,
            }]

    knowledge = AzureAISearchKnowledgeBase(
        endpoint="https://example.search.windows.net", api_key="fake",
        index_name="releaseguard-policies", embedding_deployment="embed-deployment",
        openai_endpoint="https://example.openai.azure.com", openai_api_key="fake",
        dimensions=2, search_client=Search(), index_client=object(),
        embedding_client=Embeddings(),
        vector_query_factory=lambda **kwargs: type("VectorQuery", (), kwargs)(),
    )
    results = knowledge.retrieve("TLS certificate validation")
    assert len(results) == 1
    assert results[0].citation == "security.md#TLS"
    assert results[0].score == 0.91
