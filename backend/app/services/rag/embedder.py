"""
Query embedding for RAG retrieval (Azure AI Foundry).
Same Foundry resource as chat; used only when CAVCO_SPECIFIC path runs.
"""
from __future__ import annotations

import logging
import os
from typing import List

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def get_query_embedding(text: str) -> List[float]:
    """
    Return embedding vector for the query (single string).
    Uses Azure AI Foundry embeddings deployment; same endpoint as chat.
    """
    deployment = getattr(
        settings,
        "azure_foundry_embedding_deployment",
        None,
    ) or os.environ.get("AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT")
    if not deployment:
        raise RuntimeError(
            "Embedding deployment not configured. Set azure_foundry_embedding_deployment or AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT."
        )
    endpoint = settings.azure_foundry_endpoint.rstrip("/")
    api_version = settings.azure_foundry_api_version
    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.azure_foundry_api_key,
    }
    payload = {"input": text}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]
