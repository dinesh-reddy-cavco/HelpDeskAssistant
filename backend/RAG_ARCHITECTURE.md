# RAG Chat Architecture

## 1. Architecture Overview

The chatbot uses a **decision flow** so that generic questions never hit the vector DB and Cavco-specific questions are answered only from retrieved context.

```
User query
    │
    ▼
┌─────────────────────┐
│ intent_classifier   │  LLM-based: GENERIC | CAVCO_SPECIFIC | UNKNOWN
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
  GENERIC    CAVCO_SPECIFIC / UNKNOWN
     │           │
     ▼           ▼
┌─────────┐  ┌─────────────┐
│ Foundry │  │ retriever   │  Azure AI Search (hybrid: vector + keyword)
│ only    │  └──────┬──────┘
└────┬────┘         │
     │              ▼
     │         ┌─────────────────┐
     │         │ rag_prompt_     │  Build system + user with context
     │         │ builder         │
     │         └────────┬────────┘
     │                   │
     │                   ▼
     │         ┌─────────────────┐
     │         │ answer_         │  Generate from context only
     │         │ generator       │
     │         └────────┬────────┘
     │                   │
     │                   ▼
     │         ┌─────────────────┐
     │         │ confidence_     │  Score 0–1; gate if < threshold
     │         │ scorer          │
     │         └────────┬────────┘
     │                   │
     └─────────┬────────┘
               ▼
        ┌──────────────┐
        │ main_chat_   │  Orchestrate; return answer_type, sources, confidence
        │ service      │
        └──────────────┘
```

### Constraints

- **Do not mix generic and RAG answers.** Generic path uses Foundry only; RAG path uses retrieval + Foundry with context-only prompt.
- **Generic questions must never hit the vector DB.** Intent classifier runs first; only CAVCO_SPECIFIC / UNKNOWN trigger retrieval.
- **RAG answers must never rely on LLM prior knowledge.** System prompt enforces "answer ONLY from provided context"; if not found, say so.
- **Confidence gating:** If `confidence_score < threshold` (e.g. 0.65), return escalation message and `answer_type = "ESCALATION_REQUIRED"`; do not hallucinate.

---

## 2. Folder Structure

```
backend/
  app/
    config.py              # + Azure Search, RAG, embedding deployment
    models.py              # + SourceDocument, answer_type, confidence_score, sources
    main.py                # Uses MainChatService (RAG flow)
    services/
      openai_service.py    # + system_prompt_override for RAG/intent
      logging_service.py
      feedback_service.py
      rag/
        __init__.py
        prompts.py             # Sample prompts (intent, RAG, confidence)
        intent_classifier.py   # LLM classification → GENERIC | CAVCO_SPECIFIC | UNKNOWN
        embedder.py            # Query embedding (Foundry)
        retriever.py           # Azure AI Search hybrid retrieval
        rag_prompt_builder.py   # Build system + user with context
        answer_generator.py    # Generate from context only
        confidence_scorer.py   # 0–1 score (LLM or heuristic)
        main_chat_service.py   # Orchestration
  RAG_ARCHITECTURE.md
```

---

## 3. Key Modules

### intent_classifier.py

- **Role:** Classify user message into `GENERIC`, `CAVCO_SPECIFIC`, or `UNKNOWN` using the LLM (not regex).
- **Input:** `user_query: str`
- **Output:** `Literal["GENERIC", "CAVCO_SPECIFIC", "UNKNOWN"]`
- **Decision:** One completion call with a dedicated system prompt; low temperature.

### retriever.py

- **Role:** Hybrid retrieval (vector + keyword) via Azure AI Search SDK.
- **Data source:** The **same vector store** built by the **ingestion module** (Confluence). The ingestion pipeline (ingestion/) indexes Confluence pages as chunks into Azure AI Search; this retriever queries that index. Field names (`content`, `embedding`, `page_id`, `page_title`, `section_title`, `url`, `source_type`) match the ingestion index schema. Optional filter `source_type eq 'confluence'` keeps retrieval Confluence-only; when ticket ingestion is added, the filter can be extended.
- **Input:** `query: str`, `top_k: int`, optional `source_type_filter` (default `"confluence"`).
- **Output:** `List[SourceDocument]` with `source_type`, `source_id`, `title`, `chunk_text`, `url`.
- **Decision:** Embed query with Foundry; run search with `search_text` + `vector_queries`; map hits to `SourceDocument`.

### rag_prompt_builder.py

- **Role:** Build system and user messages for RAG so the model answers only from context.
- **Input:** `user_query: str`, `documents: List[SourceDocument]`
- **Output:** `(system_prompt, user_message)` with context block; context truncated if too long.

### answer_generator.py

- **Role:** Generate answer using only provided context (no prior knowledge).
- **Input:** `user_query`, `documents`, optional `temperature` / `max_tokens`
- **Output:** `str` (answer text). Uses RAG system prompt override.

### confidence_scorer.py

- **Role:** Assign confidence 0–1 for RAG answers (for gating).
- **Options:** LLM self-evaluation (default) or heuristic (fallback).
- **Output:** `float` in [0, 1]. Used to decide ESCALATION_REQUIRED when below threshold.

### main_chat_service.py

- **Role:** Orchestrate full flow: classify → generic path or RAG path → log → return `ChatResponse`.
- **Returns:** `answer_text` (as `response`), `confidence_score`, `answer_type` (GENERIC | RAG | ESCALATION_REQUIRED), `sources` (RAG only), `requires_escalation`.

---

## 4. Sample Prompts

### Intent classification

- **System:** Defines labels (GENERIC = general IT; CAVCO_SPECIFIC = Cavco tools/policies/KB; UNKNOWN = unclear). Instructs: respond with one word only.
- **User:** `Classify this user message: "{user_query}" Answer with one word only: GENERIC, CAVCO_SPECIFIC, or UNKNOWN.`

### RAG answer generation

- **System:** You are an IT help desk assistant for Cavco. Answer **ONLY** using the provided context. If the answer is not in the context, say you couldn't find it and suggest a support ticket. Do not use prior knowledge.
- **User:** Context block (documents with headers) + `---` + `User question: {user_query}` + instruction to use only context.

### Confidence scoring

- **System:** You are a confidence evaluator. Given question and answer (from context), output a number 0–1. No explanation.
- **User:** `Question: {user_query}` + `Answer: {answer_text}` + `Score the confidence (0–1). Reply with only the number.`

(Exact strings live in `app/services/rag/prompts.py`.)

---

## 5. Configuration (env)

- **Azure AI Search:** `azure_search_endpoint`, `azure_search_key`, `azure_search_index_name`. Use the **same index name** as the ingestion module (e.g. `confluence-chunks`). The RAG retriever reads from the index that ingestion populates (Confluence chunks).
- **Embeddings:** `azure_foundry_embedding_deployment` (or `AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT`) for query embedding. Must match the embedding model used by ingestion so vectors are comparable.
- **RAG:** `rag_top_k`, `confidence_threshold` (e.g. 0.65), `escalation_message`.

---

## 6. Logging

For every request the pipeline logs:

- `user_query`
- `intent` (GENERIC / CAVCO_SPECIFIC / UNKNOWN)
- `retrieval_used` (true/false)
- `document_ids` (when retrieval used)
- `confidence_score`
- `answer_type` / `final_decision`

(Structured logging in `main_chat_service` and in the FastAPI chat endpoint.)

---

## 7. Ticket Creation

Ticket creation is **not** implemented. When `answer_type == "ESCALATION_REQUIRED"`, the API returns the configured escalation message only; no ticket is created.
