"""
Configuration for the offline ingestion service.
All values are config-driven; no hardcoded secrets or resource names.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _env(key: str, default: Optional[str] = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise ValueError(f"Missing required env var: {key}")
    return val


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    return int(raw) if raw is not None else default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


@dataclass
class ConfluenceConfig:
    """Confluence REST API settings."""
    base_url: str = field(default_factory=lambda: _env("CONFLUENCE_BASE_URL"))
    email: str = field(default_factory=lambda: _env("CONFLUENCE_EMAIL"))
    api_token: str = field(default_factory=lambda: _env("CONFLUENCE_API_TOKEN"))
    space_key: str = field(default_factory=lambda: _env("CONFLUENCE_SPACE_KEY"))
    page_limit: int = field(default_factory=lambda: _env_int("CONFLUENCE_PAGE_LIMIT", 1000))


@dataclass
class ChunkingConfig:
    """Chunking parameters for RAG."""
    target_tokens: int = field(default_factory=lambda: _env_int("CHUNK_TARGET_TOKENS", 500))
    min_tokens: int = field(default_factory=lambda: _env_int("CHUNK_MIN_TOKENS", 400))
    max_tokens: int = field(default_factory=lambda: _env_int("CHUNK_MAX_TOKENS", 600))
    overlap_tokens: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP_TOKENS", 75))
    overlap_min: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP_MIN", 50))
    overlap_max: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP_MAX", 100))


@dataclass
class AzureFoundryConfig:
    """Azure AI Foundry (embeddings). Not Azure OpenAI resource."""
    endpoint: str = field(default_factory=lambda: _env("AZURE_FOUNDRY_ENDPOINT"))
    api_key: str = field(default_factory=lambda: _env("AZURE_FOUNDRY_API_KEY"))
    api_version: str = field(default_factory=lambda: _env("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview"))
    embedding_deployment: str = field(default_factory=lambda: _env("AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT"))
    embedding_dimensions: int = field(default_factory=lambda: _env_int("AZURE_FOUNDRY_EMBEDDING_DIMENSIONS", 1536))
    batch_size: int = field(default_factory=lambda: _env_int("EMBEDDING_BATCH_SIZE", 10))


@dataclass
class AzureSearchConfig:
    """Azure AI Search settings."""
    endpoint: str = field(default_factory=lambda: _env("AZURE_SEARCH_ENDPOINT"))
    admin_key: str = field(default_factory=lambda: _env("AZURE_SEARCH_KEY"))
    index_name: str = field(default_factory=lambda: os.environ.get("AZURE_SEARCH_INDEX_NAME", "confluence-chunks"))
    skip_index_create: bool = field(default_factory=lambda: _env_bool("INGESTION_SKIP_INDEX_CREATE", False))


@dataclass
class IngestionConfig:
    """Aggregate configuration for ingestion."""
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    azure_foundry: AzureFoundryConfig = field(default_factory=AzureFoundryConfig)
    azure_search: AzureSearchConfig = field(default_factory=AzureSearchConfig)
    source_type: str = "confluence"
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "IngestionConfig":
        """Load config from environment, optionally loading from .env file."""
        if env_file is not None and env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
        return cls()
