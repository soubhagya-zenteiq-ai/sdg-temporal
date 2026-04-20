# 🧠 Temporal RAG Pipeline Deep Dive

This document explains the core mechanics, design decisions, and data architecture of the SDG Temporal RAG (Retrieval-Augmented Generation) ingestion pipeline.

---

## 1. The Core Architecture

The system transitions away from linear, script-based processing into a highly resilient **Orchestrated Architecture** powered by Temporal.

### Why Temporal?
- **Infinite Retries**: Local LLMs (like the 1.2B Instruct model used) can occasionally fail due to memory spikes or context limits. Temporal catches these `Activity` failures and transparently retries them.
- **Massive Parallelization**: Instead of waiting for Chunk 1 to process before moving to Chunk 2, Temporal dispatches all chunks to the LLM worker pool simultaneously.
- **Idempotency**: If the pipeline crashes midway, restarting it does not duplicate data; Temporal knows exactly which activities succeeded and which ones to retry.

---

## 2. The Data Flow Pipeline

The system processes documents in a strict sequence of Activities coordinated by the `MarkdownProcessingWorkflow`.

### Step A: Parsing (`parse_md.py`)
- Reads the raw Markdown file.
- Strips out excess whitespace and extracts any top-level metadata to generate a clean "Document" entity.

### Step B: Chunking (`chunk_md.py`)
- **What it does**: Slices the large text into smaller ~1000-character pieces.
- **Why it matters**: 
  1. **Context Limits**: Prevents the LLM from overflowing its context window.
  2. **Precision**: Smaller contexts force the LLM to generate highly specific, granular summaries instead of vague overviews.
  3. **Speed**: Enables Temporal to fan out the workload.

### Step C: AI Generation (The "Fan Out")
Once chunked, the workflow uses `asyncio.gather` to execute two parallel tracks *for every single chunk*:
1. **`generate_kb.py`**: Extracts a structured summary, key points, entities, and relationships. (Yields exactly 1 KB record per chunk).
2. **`generate_qa.py`**: Generates high-quality Q&A pairs. (Yields roughly 2-5 questions per chunk depending on information density).

### Step D: Database Storage (`store_results.py`)
- Takes the gathered Intelligence and persists it into PostgreSQL using SQLAlchemy. 
- Uses `ON CONFLICT DO NOTHING` or `UPDATE` statements to ensure the database remains perfectly clean no matter how many times a document is reprocessed.

---

## 3. Data Relationships & Tracking Unique Information

The database operates on a strict hierarchy:

*   **`documents`**: The root entry.
    *   **`chunks`**: Linked to `documents` via `document_id`.
        *   **`knowledge_base`**: Linked to `chunks` via `chunk_id`. (Ratio: 1-to-1)
    *   **`qa_pairs`**: Linked to `documents` via `document_id` but generated *from* chunks. (Ratio: 1-to-Many).

**Uniqueness Check**:
We enforce `UNIQUE` database constraints (e.g., `UNIQUE(file_path)` for documents, and `UNIQUE(document_id, chunk_index)` for chunks). This guarantees that reprocessing the exact same data will update/skip it, rather than duplicating information.

---

## 4. LLM Engineering & Overcoming "Blabbering"

Local, small LLMs (like 1.2B models) have a tendency to "blabber"—they add conversational text like *"Sure! Here is the JSON list you requested:"* before outputting the actual arrays. This breaks standard `.json()` parsers and initially resulted in **0 QA pairs** being stored.

We solved this using advanced **Grammar-Constrained Sampling** within `llama-cpp-python`:

1. **Constrained Output**: We pass the LLM a strict grammar mapping (derived from our desired JSON schemas). This physically prevents the LLM from picking tokens that violate the JSON structure.
2. **Larger Breathing Room**: We increased the `LLM_MAX_TOKENS` environment variable to `2048`. This ensures the AI doesn't get cut off mid-thought while generating large lists of QA pairs.
3. **Resilient Parsing**: We implemented Regex lookbacks (`r'\[.*\]'`) in the `safe_parse` functions to extract the JSON payload even if the LLM slips a Markdown backtick (```` ```json ````) into the output.

---

## 5. Local Hardware Acceleration (GPU)

Because the pipeline supports a Hybrid Local Setup, the Worker node runs directly on your machine's hardware while leveraging Docker for Postgres and Temporal. This allows you to bypass the virtualization layer to grant `llama-cpp-python` direct access to CPUs and GPUs, enabling rapid generation speeds.
