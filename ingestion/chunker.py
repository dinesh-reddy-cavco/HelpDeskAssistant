"""
Structure-aware chunking for RAG.
Section/header-based when possible; recursive fallback. Target ~400–600 tokens, overlap ~50–100.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from .config import ChunkingConfig
from .parser import StructuredSection

logger = logging.getLogger(__name__)


def count_tokens_approx(text: str) -> int:
    """Approximate token count (~4 chars per token for English). For exact use tiktoken if available."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(0, len(text) // 4)


@dataclass
class Chunk:
    """One chunk with metadata for indexing."""
    content: str
    section_title: str | None
    token_count: int

    def with_metadata(
        self,
        chunk_id: str,
        source_type: str,
        space_key: str,
        page_id: str,
        page_title: str,
        url: str,
        last_updated: str,
        version: int,
    ) -> dict:
        """Build document dict for Azure AI Search."""
        return {
            "id": chunk_id,
            "content": self.content,
            "source_type": source_type,
            "space_key": space_key,
            "page_id": page_id,
            "page_title": page_title,
            "section_title": self.section_title or "",
            "url": url,
            "last_updated": last_updated,
            "version": version,
        }


def _split_recursive(
    text: str,
    config: ChunkingConfig,
    section_title: str | None,
) -> list[Chunk]:
    """Split text by paragraphs/sentences to fit target size with overlap."""
    if not text.strip():
        return []
    tokens = count_tokens_approx(text)
    if tokens <= config.max_tokens:
        return [Chunk(content=text.strip(), section_title=section_title, token_count=tokens)]

    # Split by double newline first, then single, then sentence
    parts = re.split(r"\n\s*\n", text)
    chunks: list[Chunk] = []
    buffer = ""
    buffer_tokens = 0
    overlap_text = ""
    overlap_tokens = 0

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        pt = count_tokens_approx(part)
        if buffer_tokens + pt <= config.max_tokens:
            buffer = f"{buffer}\n\n{part}".strip() if buffer else part
            buffer_tokens = count_tokens_approx(buffer)
            continue
        # Flush buffer
        if buffer:
            chunks.append(Chunk(content=buffer, section_title=section_title, token_count=buffer_tokens))
            # Overlap: take last N tokens from buffer
            words = buffer.split()
            overlap_size = min(config.overlap_max, max(config.overlap_min, len(words) // 2))
            overlap_text = " ".join(words[-overlap_size:]) if overlap_size else ""
            overlap_tokens = count_tokens_approx(overlap_text)
        # Start new buffer with overlap
        buffer = f"{overlap_text}\n\n{part}".strip() if overlap_text else part
        buffer_tokens = count_tokens_approx(buffer)

    if buffer:
        chunks.append(Chunk(content=buffer, section_title=section_title, token_count=count_tokens_approx(buffer)))
    return chunks


def _section_to_chunks(section: StructuredSection, config: ChunkingConfig) -> list[Chunk]:
    """Chunk one section: prefer by size; if over max, recursive split."""
    title = section.heading or ""
    text = section.text.strip()
    if not text and not title:
        return []
    if title:
        text = f"{title}\n\n{text}"
    tokens = count_tokens_approx(text)
    if tokens <= config.max_tokens:
        return [Chunk(content=text, section_title=section.heading, token_count=tokens)]
    return _split_recursive(text, config, section.heading)


def _merge_small_chunks(chunks: list[Chunk], config: ChunkingConfig) -> list[Chunk]:
    """
    Merge consecutive chunks that are below min_tokens so we approach target size.
    Stops merging when adding the next chunk would exceed max_tokens.
    """
    if not chunks:
        return []
    merged: list[Chunk] = []
    buffer = chunks[0]
    for i in range(1, len(chunks)):
        next_ch = chunks[i]
        combined_tokens = buffer.token_count + count_tokens_approx("\n\n") + next_ch.token_count
        # Merge if: combined fits in max, and at least one is small (below min_tokens)
        should_merge = (
            combined_tokens <= config.max_tokens
            and (buffer.token_count < config.min_tokens or next_ch.token_count < config.min_tokens)
        )
        if should_merge:
            new_content = f"{buffer.content}\n\n{next_ch.content}"
            new_tokens = count_tokens_approx(new_content)
            titles = [t for t in (buffer.section_title, next_ch.section_title) if t]
            new_title = " | ".join(titles) if titles else buffer.section_title
            buffer = Chunk(content=new_content, section_title=new_title or None, token_count=new_tokens)
        else:
            merged.append(buffer)
            buffer = next_ch
    merged.append(buffer)
    return merged


def chunk_sections(sections: list[StructuredSection], config: ChunkingConfig | None = None) -> list[Chunk]:
    """
    Structure-aware chunking: one chunk per section when small enough;
    otherwise split section with overlap. Then merge small consecutive chunks
    so we approach target size (fewer, larger chunks when sections are tiny).
    """
    cfg = config or ChunkingConfig()
    chunks: list[Chunk] = []
    for s in sections:
        chunks.extend(_section_to_chunks(s, cfg))
    return _merge_small_chunks(chunks, cfg)


def chunk_plain_text(text: str, config: ChunkingConfig | None = None) -> list[Chunk]:
    """Fallback: chunk plain text with recursive split (no section titles)."""
    return _split_recursive(text, config or ChunkingConfig(), section_title=None)


def make_chunk_id(page_id: str, section_title: str | None, chunk_index: int) -> str:
    """Stable unique id for a chunk (idempotent re-indexing)."""
    raw = f"{page_id}|{section_title or ''}|{chunk_index}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{page_id}_{h}_{chunk_index}"
