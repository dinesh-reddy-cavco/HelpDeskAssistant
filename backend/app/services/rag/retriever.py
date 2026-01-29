"""
Retrieval using Azure AI Search: vector + keyword (hybrid).

This module queries the **same vector store** that is built and populated by the
ingestion module (see ingestion/). The ingestion pipeline indexes Confluence
pages as chunks into Azure AI Search; we retrieve from that index only.
Field names (content, embedding, page_id, page_title, section_title, url,
source_type) match the ingestion index schema. When ticket ingestion is added
later, filter by source_type to restrict to confluence or tickets.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from app.config import settings
from app.models import SourceDocument
from app.services.rag.embedder import get_query_embedding

logger = logging.getLogger(__name__)

# Index schema is defined by ingestion (ingestion/azure_search_index.py).
# Fields: id, content, embedding, source_type, space_key, page_id, page_title, section_title, url, ...
DEFAULT_SOURCE_TYPE = "confluence"  # Ingestion module indexes Confluence; filter when multiple sources exist


def _get_search_client() -> SearchClient:
    """Lazy client for Azure AI Search (same index as ingestion module)."""
    if not settings.azure_search_endpoint or not settings.azure_search_key:
        raise RuntimeError("Azure AI Search is not configured (azure_search_endpoint, azure_search_key)")
    return SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_key),
    )


def retrieve(
    query: str,
    top_k: int | None = None,
    *,
    use_hybrid: bool = True,
    source_type_filter: Optional[str] = DEFAULT_SOURCE_TYPE,
) -> List[SourceDocument]:
    """
    Retrieve top-k chunks from the vector store built by the ingestion module (Confluence).

    Queries the same Azure AI Search index populated by ingestion/ (confluence_client →
    parser → chunker → embedder → azure_search_index). Hybrid search: vector + keyword.
    Returns list of SourceDocument with source_type, source_id, title, chunk_text, url.
    """
    k = top_k if top_k is not None else settings.rag_top_k
    client = _get_search_client()

    query_vector = get_query_embedding(query)
    vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=k, fields="embedding")

    # Optional filter: restrict to Confluence chunks (ingestion source); extend later for tickets
    filter_expr = f"source_type eq '{source_type_filter}'" if source_type_filter else None

    if use_hybrid:
        results = client.search(
            search_text=query,
            vector_queries=[vector_query],
            top=k,
            select=["id", "content", "source_type", "page_id", "page_title", "section_title", "url"],
            filter=filter_expr,
        )
    else:
        results = client.search(
            vector_queries=[vector_query],
            top=k,
            select=["id", "content", "source_type", "page_id", "page_title", "section_title", "url"],
            filter=filter_expr,
        )

    docs: List[SourceDocument] = []
    for r in results:
        docs.append(
            SourceDocument(
                source_type=r.get("source_type") or DEFAULT_SOURCE_TYPE,
                source_id=r.get("page_id") or r.get("id", ""),
                title=r.get("page_title") or "",
                chunk_text=r.get("content") or "",
                url=r.get("url"),
                section_title=r.get("section_title"),
            )
        )
    return docs
