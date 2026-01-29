"""
Orchestration for offline Confluence → Azure AI Search ingestion.
Idempotent: safe to re-run; chunks are upserted by stable id.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .config import IngestionConfig
from .confluence_client import ConfluenceClient
from .parser import html_to_sections
from .chunker import chunk_sections, make_chunk_id
from .embedder import Embedder
from .azure_search_index import AzureSearchIndex

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Stats for one ingestion run."""
    pages_fetched: int = 0
    chunks_created: int = 0
    chunks_uploaded: int = 0
    errors: List[str] = field(default_factory=list)

    def log_summary(self) -> None:
        logger.info(
            "Ingestion complete: pages=%d chunks=%d uploaded=%d errors=%d",
            self.pages_fetched,
            self.chunks_created,
            self.chunks_uploaded,
            len(self.errors),
        )
        for e in self.errors:
            logger.error("Ingestion error: %s", e)


def run_ingestion(
    config: IngestionConfig | None = None,
    env_file: Path | None = None,
    space_key: str | None = None,
) -> IngestionStats:
    """
    Full pipeline: fetch pages → parse → chunk → embed → upsert.
    Config is loaded from env (and optional env_file). Optional space_key overrides config.
    """
    if config is None:
        config = IngestionConfig.from_env(env_file)
    stats = IngestionStats()

    # 1. Fetch pages
    client = ConfluenceClient(config.confluence)
    try:
        pages = client.fetch_all_pages_in_space(space_key or config.confluence.space_key)
    except Exception as e:
        stats.errors.append(f"Confluence fetch: {e}")
        return stats
    stats.pages_fetched = len(pages)

    # 2. Parse, chunk, collect all chunk payloads (content + metadata for embed + index)
    chunk_payloads: List[dict] = []
    for page in pages:
        sections = html_to_sections(page.html_content)
        chunks = chunk_sections(sections, config.chunking)
        last_updated = (page.last_updated or "")[:50]  # truncate for index
        for i, ch in enumerate(chunks):
            chunk_id = make_chunk_id(page.page_id, ch.section_title, i)
            chunk_payloads.append({
                "chunk_id": chunk_id,
                "content": ch.content,
                "section_title": ch.section_title,
                "source_type": config.source_type,
                "space_key": page.space_key,
                "page_id": page.page_id,
                "page_title": page.title,
                "url": page.url,
                "last_updated": last_updated,
                "version": page.version,
            })
    stats.chunks_created = len(chunk_payloads)

    if not chunk_payloads:
        logger.warning("No chunks to ingest")
        return stats

    # 3. Embeddings (batch)
    embedder = Embedder(config.azure_foundry)
    try:
        texts = [p["content"] for p in chunk_payloads]
        embeddings = embedder.embed_batch(texts)
    except Exception as e:
        stats.errors.append(f"Embedding: {e}")
        return stats

    # 4. Build index documents and upsert
    search_index = AzureSearchIndex(
        search_config=config.azure_search,
        embedding_dimensions=config.azure_foundry.embedding_dimensions,
    )
    if not config.azure_search.skip_index_create:
        try:
            search_index.ensure_index(config.azure_foundry.embedding_dimensions)
        except Exception as e:
            err_msg = str(e).lower()
            hint = (
                " Check AZURE_SEARCH_ENDPOINT (e.g. https://<name>.search.windows.net) and "
                "network/DNS (firewall, VPN). If the index already exists, set INGESTION_SKIP_INDEX_CREATE=1 to skip create."
            )
            if "resolve" in err_msg or "timeout" in err_msg or "getaddrinfo" in err_msg:
                raise ConnectionError(f"Cannot reach Azure AI Search: {e}{hint}") from e
            raise
    else:
        logger.info("Skipping index create (INGESTION_SKIP_INDEX_CREATE=1)")
    docs = []
    for p, emb in zip(chunk_payloads, embeddings):
        docs.append(search_index.doc_from_chunk_meta(
            chunk_id=p["chunk_id"],
            content=p["content"],
            embedding=emb,
            source_type=p["source_type"],
            space_key=p["space_key"],
            page_id=p["page_id"],
            page_title=p["page_title"],
            section_title=p["section_title"] or "",
            url=p["url"],
            last_updated=p["last_updated"],
            version=p["version"],
        ))
    try:
        search_index.upload_documents(docs)
        stats.chunks_uploaded = len(docs)
    except Exception as e:
        stats.errors.append(f"Upload: {e}")

    return stats


def main() -> int:
    """CLI entry: run ingestion and exit with 0 on success, 1 on failure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    config = IngestionConfig.from_env(env_path)
    stats = run_ingestion(config=config, env_file=env_path)
    stats.log_summary()
    return 0 if not stats.errors else 1


if __name__ == "__main__":
    sys.exit(main())
