"""
Azure AI Search index definition and document upload.
Supports vector search, keyword search, and semantic ranking.
"""
from __future__ import annotations

import logging
from typing import Any, List

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
)

# Semantic search (optional; SDK version may vary)
try:
    from azure.search.documents.indexes.models import (
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
    )
    _SEMANTIC_AVAILABLE = True
except ImportError:
    _SEMANTIC_AVAILABLE = False

from .config import AzureSearchConfig, AzureFoundryConfig

logger = logging.getLogger(__name__)


def build_index_schema(
    index_name: str,
    embedding_dimensions: int,
    vector_profile_name: str = "vector_profile",
    semantic_config_name: str = "default",
) -> SearchIndex:
    """
    Index schema for hybrid + semantic search.
    Fields: id, content (searchable), embedding (vector), source_type, space_key,
    page_id, page_title, section_title, url, last_updated, version (all filterable/retrievable).
    """
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
            retrievable=True,
        ),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=embedding_dimensions,
            vector_search_profile_name=vector_profile_name,
        ),
        SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="space_key", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="page_id", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="page_title", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="section_title", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="url", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="last_updated", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="version", type=SearchFieldDataType.Int32, filterable=True, retrievable=True),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name=vector_profile_name, algorithm_configuration_name="hnsw")],
    )
    index_kw: dict = {
        "name": index_name,
        "fields": fields,
        "vector_search": vector_search,
    }
    if _SEMANTIC_AVAILABLE:
        index_kw["semantic_search"] = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=semantic_config_name,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="page_title"),
                        content_fields=[SemanticField(field_name="content")],
                        keywords_fields=[SemanticField(field_name="section_title")],
                    ),
                )
            ],
            default_configuration_name=semantic_config_name,
        )
    return SearchIndex(**index_kw)


class AzureSearchIndex:
    """Create/update index and upload chunk documents."""

    def __init__(
        self,
        search_config: AzureSearchConfig | None = None,
        embedding_dimensions: int | None = None,
    ):
        self.search_config = search_config or AzureSearchConfig()
        self._embed_dims = embedding_dimensions
        self._index_client = SearchIndexClient(
            self.search_config.endpoint,
            AzureKeyCredential(self.search_config.admin_key),
        )
        self._search_client: SearchClient | None = None

    def ensure_index(self, embedding_dimensions: int) -> None:
        """Create or update the index with the given embedding dimensions."""
        schema = build_index_schema(
            self.search_config.index_name,
            embedding_dimensions=embedding_dimensions,
        )
        self._index_client.create_or_update_index(schema)
        logger.info("Index %s created/updated", self.search_config.index_name)

    @property
    def search_client(self) -> SearchClient:
        if self._search_client is None:
            self._search_client = SearchClient(
                self.search_config.endpoint,
                self.search_config.index_name,
                AzureKeyCredential(self.search_config.admin_key),
            )
        return self._search_client

    def upload_documents(self, documents: List[dict[str, Any]]) -> None:
        """Upsert documents (idempotent). Batch in chunks to avoid timeouts."""
        if not documents:
            return
        batch_size = 1000
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            result = self.search_client.upload_documents(batch)
            failed = [r for r in result if not r.succeeded]
            if failed:
                for r in failed:
                    logger.error("Document upload failed: %s", r.key)
            logger.debug("Uploaded batch %d-%d", i, i + len(batch))

    def doc_from_chunk_meta(
        self,
        chunk_id: str,
        content: str,
        embedding: list[float],
        source_type: str,
        space_key: str,
        page_id: str,
        page_title: str,
        section_title: str,
        url: str,
        last_updated: str,
        version: int,
    ) -> dict[str, Any]:
        """Build one index document from chunk and metadata."""
        return {
            "id": chunk_id,
            "content": content,
            "embedding": embedding,
            "source_type": source_type,
            "space_key": space_key,
            "page_id": page_id,
            "page_title": page_title,
            "section_title": section_title or "",
            "url": url,
            "last_updated": last_updated or "",
            "version": version,
        }
