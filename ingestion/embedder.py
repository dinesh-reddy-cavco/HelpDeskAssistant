"""
Embedding generation via Azure AI Foundry (not Azure OpenAI resource).
Uses deployments under the Foundry endpoint; supports batch for throughput.
"""
from __future__ import annotations

import logging
from typing import List

import requests

from .config import AzureFoundryConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using Azure AI Foundry embeddings API."""

    def __init__(self, config: AzureFoundryConfig | None = None):
        self.config = config or AzureFoundryConfig()
        self._base = self.config.endpoint.rstrip("/")
        self._url = (
            f"{self._base}/openai/deployments/{self.config.embedding_deployment}"
            f"/embeddings?api-version={self.config.api_version}"
        )
        self._headers = {
            "Content-Type": "application/json",
            "api-key": self.config.api_key,
        }

    def embed_one(self, text: str) -> list[float]:
        """Return embedding vector for a single string."""
        payload = {"input": text}
        r = requests.post(self._url, headers=self._headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    def embed_batch(self, texts: List[str]) -> List[list[float]]:
        """
        Return list of embedding vectors. API accepts multiple inputs in one call.
        If batch is large, chunks into config.batch_size to avoid limits.
        """
        if not texts:
            return []
        batch_size = self.config.batch_size
        all_embeddings: List[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {"input": batch}
            r = requests.post(self._url, headers=self._headers, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json().get("data", [])
            # API returns in same order as input
            order = {d["index"]: d["embedding"] for d in data}
            all_embeddings.extend([order[j] for j in range(len(batch))])
        return all_embeddings
