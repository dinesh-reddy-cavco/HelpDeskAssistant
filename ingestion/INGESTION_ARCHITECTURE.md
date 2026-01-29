# Offline Ingestion Service — Architecture Overview

## Purpose

Standalone ingestion pipeline for an enterprise RAG system. **Not** part of the chatbot API. Runs on schedule (cron), manually, or in a CI/CD pipeline.

- **Source:** Confluence (single space, many pages)
- **Target:** Azure AI Search
- **Goal:** Hybrid search (vector + keyword) with rich metadata

### Running the pipeline

- **From project root only:** `python -m ingestion`  
  (Running from a subfolder like `backend/` causes `ModuleNotFoundError: No module named 'ingestion'` because the package lives at the repo root.)
- **Azure unreachable:** If you see `Failed to resolve '...search.windows.net'` (DNS) or `ServiceRequestTimeoutError`, this machine cannot reach Azure AI Search. Check:
  - **AZURE_SEARCH_ENDPOINT** is correct (e.g. `https://<your-service-name>.search.windows.net`).
  - Network/DNS: firewall, VPN, or corporate proxy allowing outbound HTTPS to `*.search.windows.net`.
- **Skip index create:** If the index already exists (e.g. created in Azure portal) or create fails due to network, set `INGESTION_SKIP_INDEX_CREATE=1` so the pipeline skips create/update and goes straight to document upload (upload will still need network access).

---

## High-Level Flow

```
Confluence Space
       │
       ▼
┌──────────────────┐
│ confluence_client │  Fetch all pages (REST API, recursive children)
└────────┬─────────┘
         ▼
┌──────────────────┐
│     parser       │  HTML → clean structured text (headings preserved)
└────────┬─────────┘
         ▼
┌──────────────────┐
│     chunker      │  Structure-aware chunking (sections, then recursive)
└────────┬─────────┘
         ▼
┌──────────────────┐
│    embedder      │  Azure AI Foundry embeddings (batch)
└────────┬─────────┘
         ▼
┌──────────────────┐
│ azure_search_    │  Upsert documents (idempotent)
│     index        │
└──────────────────┘
         │
         ▼
   Azure AI Search
   (vector + keyword + semantic)
```

---

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **confluence_client** | Confluence REST: get space homepage, recursive child pages, page body + version/metadata. No parsing. |
| **parser** | HTML → plain text with structure: strip nav/noise, keep headings and hierarchy for chunker. |
| **chunker** | Section/header-based splits; then merge small consecutive chunks (below min_tokens) so chunks approach target size. Target ~400–600 tokens, overlap ~50–100. |
| **embedder** | Call Azure AI Foundry embeddings API (batch). No LangChain. |
| **azure_search_index** | Index schema definition, create/update index, document upload (upsert by `id`). |
| **ingest** | Orchestration: fetch → parse → chunk → embed → upsert; logging and stats. |

---

## Design Principles

- **Idempotent:** Re-running ingestion overwrites/upserts by stable chunk `id`; safe to re-run.
- **Config-driven:** No hardcoded URLs, keys, or space names; use env/config.
- **Extensible:** Same pipeline shape can later support ticket ingestion (new client + parser, same chunker/embedder/index).
- **Explicit code:** No LangChain; direct API calls and clear logic.

---

## Index Schema (Azure AI Search)

See **Index schema** section below and `azure_search_index.py` for the full field list. Summary:

- **id** — Unique chunk id (e.g. `{page_id}_{section_hash}_{chunk_index}`).
- **content** — Chunk text (searchable; used for keyword + semantic).
- **embedding** — Vector field for k-NN.
- **Metadata fields** — source_type, space_key, page_id, page_title, section_title, url, last_updated, version (all filterable/retrievable).

---

## Scaling and Re-indexing

- **Full re-index:** Run ingest for the space; upserts replace existing chunks for that space/pages. Optionally delete-by-space before run for a clean slate.
- **Incremental (future):** Track `last_updated` per page; only fetch pages modified since last run; upsert only changed pages’ chunks (and remove chunks for deleted pages if desired).
- **Parallelism:** Embedding and search upload can be batched; Confluence fetch can be parallel per page with rate limiting.
- **Large spaces:** Process pages in batches; commit to Azure Search in chunks (e.g. 1000 docs per batch) to avoid timeouts.

Details in **Notes on scaling and re-indexing** at the end of this doc.

---

## Index Schema (Full)

| Field | Type | Searchable | Filterable | Retrievable | Notes |
|-------|------|------------|------------|-------------|-------|
| id | string | key | — | ✓ | Unique chunk id (stable for idempotent upsert) |
| content | string | ✓ | — | ✓ | Chunk text; keyword + semantic |
| embedding | Collection(Single) | vector | — | ✓ | Vector for k-NN; dimensions from config |
| source_type | string | — | ✓ | ✓ | e.g. "confluence" |
| space_key | string | — | ✓ | ✓ | Confluence space key |
| page_id | string | — | ✓ | ✓ | Confluence page id |
| page_title | string | ✓ | ✓ | ✓ | Page title |
| section_title | string | — | ✓ | ✓ | Section/heading for chunk |
| url | string | — | ✓ | ✓ | Confluence page URL |
| last_updated | string | — | ✓ | ✓ | Page version date |
| version | int32 | — | ✓ | ✓ | Confluence page version number |

- **Vector search:** HNSW profile on `embedding`.
- **Semantic search:** When SDK supports it, semantic configuration uses `page_title` as title, `content` as content, `section_title` as keywords.

---

## Notes on Scaling and Re-indexing

### Full re-index (current)

- Run `ingest.run_ingestion()` for the space. Chunk ids are derived from `page_id`, `section_title`, and chunk index, so re-running **upserts** the same chunks (idempotent).
- If you need a **clean slate** for the space: before ingest, run a filter delete on `space_key eq '<key>'` (implement a small script or use Azure portal). Then run ingest.

### Incremental (future)

- Confluence REST exposes `version.when` per page. Store last run timestamp; on next run, fetch only pages with `version.when` after that timestamp (Confluence CQL or compare after full fetch).
- For each changed page: delete existing chunks for that `page_id` (filter `page_id eq '<id>'`), then upsert new chunks. Deleted pages: delete chunks by `page_id` for pages no longer in the space tree.

### Throughput

- **Confluence:** Single-threaded fetch is simple; for large spaces, add optional parallel fetch with a small worker pool and rate limiting to avoid 429s.
- **Embeddings:** Batch size is configurable (`AZURE_FOUNDRY_EMBEDDING_BATCH_SIZE` / `EMBEDDING_BATCH_SIZE`). Increase for throughput; respect API limits.
- **Azure Search:** Upload in batches of 1000 documents; `upload_documents` is already batched in `azure_search_index.py`.

### Large spaces

- Process pages in a loop and flush chunks to search in batches (e.g. every N pages or M chunks) so memory stays bounded.
- Optional: persist chunk payloads (without embeddings) to disk and run embedder + upload in a second pass for very large runs.
