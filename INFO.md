# 🏗️ SDG Temporal Pipeline — HLD & LLD Technical Reference

This document is the authoritative technical reference for the SDG Temporal Markdown ingestion pipeline. It covers High-Level Design (HLD), Low-Level Design (LLD), all configuration parameters, data-flow mappings, and the reasoning behind every key design decision.

---

## PART 1: HIGH-LEVEL DESIGN (HLD)

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST MACHINE                            │
│                                                                 │
│  ┌──────────────┐      ┌──────────────────────────────────┐     │
│  │  CLI Trigger │─────▶│  Temporal Python Client           │     │
│  │  app.main    │      │  (Starts Workflow Execution)      │     │
│  └──────────────┘      └────────────────┬─────────────────┘     │
│                                          │  Workflow Signal      │
│  ┌─────────────────────────────────────▼─────────────────┐     │
│  │                  LOCAL WORKER PROCESS                   │     │
│  │          python3 -m app.workers.worker                  │     │
│  │                                                         │     │
│  │  ┌──────────────────────────────────────────────────┐  │     │
│  │  │         MarkdownProcessingWorkflow               │  │     │
│  │  │   parse → chunk → [KB||QA](parallel) → store    │  │     │
│  │  └──────────────────────────────────────────────────┘  │     │
│  │                                                         │     │
│  │  ┌───────────────────┐   LLM Inference                 │     │
│  │  │  llama-cpp-python  │ ◀──── Uses local CPU/GPU       │     │
│  │  │  (LFM 1.2B GGUF)  │                                 │     │
│  │  └───────────────────┘                                 │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                 │
└────────────────────────┬──────────────────────────────────────-─┘
                          │  Docker Bridge Network
┌─────────────────────────▼───────────────────────────────────────┐
│                      DOCKER CONTAINERS                          │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Temporal Server │    │  PostgreSQL  │    │  Temporal UI │  │
│  │  Port: 7233      │    │  Port: 5432  │    │  Port: 8080  │  │
│  │  (Orchestrator)  │    │  (Knowledge) │    │  (Dashboard) │  │
│  └──────────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Roles

| Component | Role | Location |
| :--- | :--- | :--- |
| `app.main` | CLI Entrypoint. Accepts `--file` or `--dir` and signals Temporal | Host |
| `Temporal Server` | Stateful Orchestrator. Holds workflow history and dispatches tasks | Docker |
| `Worker (worker.py)` | Hosts the Workflow and Activity code. Polls for tasks | Host (Local) |
| `LLMService` | Singleton LLM Engine (llama-cpp). Loaded once per worker process | Host (Local) |
| `PostgreSQL` | Persistent Knowledge Store. Stores Documents, Chunks, KB, and Q&A | Docker |
| `Temporal UI` | Visual Dashboard for monitoring workflow runs and failures | Docker |

### 1.3 Why a Hybrid Setup? (Workers Local, Infra in Docker)
This is the core architectural decision. The LLM (`llama-cpp-python`) performs hardware inference (CPU/GPU acceleration) that is very difficult and slow to properly containerize, especially without NVIDIA Docker runtime.

**Benefits:**
- ✅ Direct access to host CPU threads and GPU memory.
- ✅ No container overhead for heavy numerical computation.
- ✅ Infrastructure (Temporal, Postgres) stays isolated and reproducible in Docker.

---

## PART 2: DATA FLOW (Step-by-Step)

### 2.1 Triggering (app/main.py)

When you run `python3 -m app.main --file ./data/markdown/sample.md`:
1.  The main script resolves the absolute path of the file.
2.  It connects to the Temporal server at `localhost:7233`.
3.  It calls `client.start_workflow(MarkdownProcessingWorkflow.run, file_path, ...)`.
4.  This creates a **Workflow Execution** in the Temporal server with a unique Run ID.
5.  The main script returns the Run ID — the workflow is now running asynchronously.

### 2.2 Activity Flow

```
file_path (string)
    │
    ▼
[Activity 1] parse_md
    │   Reads file. Extracts title. Cleans whitespace.
    │   Returns: ParsedMarkdown { file_path, title, content }
    │
    ▼
[Activity 2] chunk_md
    │   Splits content into ~1200 char pieces.
    │   Returns: List[Chunk] { chunk_index, content }
    │   e.g., 10 chunks for a medium document
    │
    ▼
    ├──── asyncio.gather() ──────────────────────────────────────┐
    │                                                            │
    │ [Activity 3x10] generate_kb_chunk                         │ [Activity 4x10] generate_qa_chunk
    │   For EACH chunk, in parallel:                            │   For EACH chunk, in parallel:
    │   - Builds KB prompt from chunk content                   │   - Builds QA prompt from chunk content
    │   - Calls LLMService.generate(prompt, schema=KB_SCHEMA)   │   - Calls LLMService.generate(prompt, schema=QA_SCHEMA)
    │   - Parses JSON into KBEntry                              │   - Parses JSON into List[QAPair]
    │   Returns: KBEntry { summary, key_points, entities, ... } │   Returns: List[QAPair] { question, answer, difficulty }
    │                                                           │   (Always returns exactly 5 pairs per chunk)
    └───────────────────────────────────────────────────────────┘
    │
    │ Workflow waits for ALL 20 futures to complete
    │ Deduplicates QA questions (case-insensitive set lookup)
    │
    ▼
[Activity 5] store_results
    │   Receives: ParsedMarkdown, chunks, kb_entries, qa_pairs
    │   1. INSERT into `documents` (ON CONFLICT DO NOTHING)
    │   2. INSERT into `chunks` (ON CONFLICT DO NOTHING)
    │   3. INSERT into `knowledge_base` (linked to chunk_id)
    │   4. INSERT into `qa_pairs` (linked to document_id)
    │   Returns: { document_id, chunks, kb_entries, qa_pairs }
```

---

## PART 3: LOW-LEVEL DESIGN (LLD)

### 3.1 Worker Configuration (app/workers/worker.py)

```python
ThreadPoolExecutor(max_workers=10)   # Thread pool for sync activities
max_concurrent_activities=5          # Max LLM jobs running at once
max_concurrent_workflow_tasks=5      # Max workflow coroutines processing
```

**Why `max_concurrent_activities=5`?**
Each LLM activity loads chunks of model KV-cache into RAM/VRAM. Running 10+ concurrently on a machine with 8-16 GB RAM can cause Out-of-Memory crashes. 5 is a safe default that leaves headroom for the OS and PostgreSQL.

**Why `ThreadPoolExecutor`?**
All activity functions (`generate_kb_chunk`, `generate_qa_chunk`, etc.) are defined as `def` (synchronous). Temporal's async event loop cannot call them directly without blocking; they must be dispatched to a thread pool. This is the standard Temporal Python SDK pattern for CPU-bound activities.

### 3.2 Chunking Configuration (app/config/settings.py)

```python
MAX_CHUNK_SIZE: int = 1200  # Characters per chunk
```

| Setting | Value | Why |
| :--- | :--- | :--- |
| `MAX_CHUNK_SIZE` | 1200 chars | ~300-350 tokens. Leaves room for the LLM prompt itself in a 4096-token context. |
| `LLM_CTX_SIZE` | 4096 | The context window of the model (max tokens it can "see" at once). |
| `LLM_MAX_TOKENS` | 2048 | Max output tokens. Must be ≥ 1000 to fit 5 full Q&A objects in JSON. |

### 3.3 LLM Inference Flow (app/services/llm_service.py)

The `LLMService` is implemented as a **Singleton** to avoid loading the 1.2GB model file more than once per worker process.

```
First call to generate():
  → _instance is None → acquire lock → load Llama model from .gguf file
  → model stored in memory (~1.5GB RAM usage)

Subsequent calls:
  → _instance already exists → skip loading → go straight to inference
  → inference_lock (threading.Lock) ensures thread-safe token generation
```

**Grammar-Constrained Sampling Logic:**
```
client code passes schema dict to generate(prompt, schema={...})
  ↓
from llama_cpp.llama_grammar import LlamaGrammar
grammar = LlamaGrammar.from_json_schema(json.dumps(schema))
  ↓
Llama model(..., grammar=grammar)
  ↓
At each token generation step:
  The token logits (probability scores for all 32,000 vocab items)
  are "masked" — invalid JSON tokens are set to -infinity probability.
  The model can ONLY pick tokens that advance the JSON state machine.
  ↓
Result: Output is 100% valid JSON, always.
```

### 3.4 KB Generation Strategy (app/activities/generate_kb.py)

**Purpose**: Extract structured facts from a chunk for use in a search index.

**Prompt Design:**
```
"Extract structured knowledge from the markdown chunk.
Return STRICT JSON:
{ summary, key_points[], entities[], relationships[] }"
```

**Schema Constraint (flat, simple for grammar compatibility):**
```json
{
  "type": "object",
  "properties": {
    "summary":       { "type": "string" },
    "key_points":    { "type": "array", "items": { "type": "string" } },
    "entities":      { "type": "array", "items": { "type": "string" } },
    "relationships": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["summary", "key_points", "entities", "relationships"]
}
```

**Ratio**: 1 KB Entry per chunk. Always.

### 3.5 QA Generation Strategy (app/activities/generate_qa.py)

**Purpose**: Generate a dense, varied set of questions covering the chunk for training or retrieval.

**Prompt Design:**
```
"Generate EXACTLY 5 high-quality Q&A pairs from the content.
You must provide exactly 5 pairs. Cover different parts of the text."
```

**Schema Constraint (enforces exactly 5 items):**
```json
{
  "type": "array",
  "minItems": 5,
  "maxItems": 5,
  "items": {
    "type": "object",
    "properties": {
      "question":   { "type": "string" },
      "answer":     { "type": "string" },
      "difficulty": { "enum": ["easy", "medium", "hard"] }
    }
  }
}
```

**Ratio**: Exactly 5 QA pairs per chunk. For a 10-chunk document → **50 total Q&A pairs**.

**Deduplication**: After all QA chunks are gathered, the workflow does a case-insensitive set-comparison to remove any accidentally repeated questions before writing to the database.

### 3.6 Database Schema (docker/postgres/init.sql)

```sql
documents   (id UUID PK, file_path TEXT UNIQUE, title, created_at)
    │
    ├── chunks   (id UUID PK, document_id FK, content TEXT, chunk_index INT)
    │       │    UNIQUE(document_id, chunk_index) ← idempotency
    │       │
    │       └── knowledge_base   (id UUID PK, chunk_id FK, summary, key_points JSONB, entities JSONB, relationships JSONB)
    │
    └── qa_pairs   (id UUID PK, document_id FK, question, answer, difficulty)
                   UNIQUE(document_id, question) ← deduplication
```

---

## PART 4: CONFIGURATION REFERENCE

### 4.1 All `.env` Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DB_HOST` | `localhost` | PostgreSQL host. Use `localhost` for local worker, `postgres` for Docker worker. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `DB_NAME` | `md_pipeline` | PostgreSQL database name. |
| `DB_USER` | `user` | PostgreSQL username. |
| `DB_PASSWORD` | `password` | PostgreSQL password. |
| `TEMPORAL_HOST` | `localhost:7233` | Temporal gRPC endpoint. Must be `localhost` for local worker. |
| `TEMPORAL_TASK_QUEUE` | `md-queue` | The named queue the worker listens on. |
| `LLM_MODEL_PATH` | `./models/your_model.gguf` | **Relative or absolute path to model file.** Must be host-accessible. |
| `LLM_CTX_SIZE` | `4096` | LLM context window. Larger = more RAM. |
| `LLM_THREADS` | `4` | CPU threads for inference. Match to your core count. |
| `LLM_GPU_LAYERS` | `0` | Number of model layers to offload to GPU. Set >0 for CUDA. |
| `LLM_MAX_TOKENS` | `2048` | Max tokens generated per call. Must be ≥1000 for 5-pair QA. |
| `LLM_TEMPERATURE` | `0.2` | LLM creativity (0=deterministic, 1=creative). Kept low for facts. |

### 4.2 Activity Timeout Configuration (app/workflows/md_workflow.py)

| Activity | `start_to_close_timeout` | `maximum_attempts` | Reason |
| :--- | :--- | :--- | :--- |
| `parse_md` | 2 min | 3 | Fast I/O. Should never fail twice. |
| `chunk_md` | 2 min | 3 | Pure CPU string ops. Very fast. |
| `generate_kb_chunk` | 5 min | 2 | LLM inference can be slow. |
| `generate_qa_chunk` | 5 min | 2 | LLM must produce 5 items. Needs more time. |
| `store_results` | 3 min | 3 | DB write. Should be fast but retried for flaky Postgres connections. |

---

## PART 5: PERFORMANCE ANALYSIS

### 5.1 Request Amplification Factor
For a single document split into N chunks:

| Step | Requests |
| :--- | :--- |
| Parse | 1 |
| Chunk | 1 |
| KB Generations | N |
| QA Generations | N |
| Store | 1 |
| **Total LLM Calls** | **2N** |

For N = 10 chunks: **20 total LLM inference calls per document.**

### 5.2 Why It Seems Slower Than Kubeflow
The Kubeflow pipeline ran **1 LLM call** per document (one big summary).  
This Temporal pipeline runs **20 LLM calls** to extract a far deeper, deduplicated, granular intelligence set.

The tradeoff is **richness vs speed**. For RAG systems, rich granular data always wins.

### 5.3 Tuning for Speed

| Goal | Change |
| :--- | :--- |
| Fewer, faster runs | Increase `MAX_CHUNK_SIZE` (e.g., 4000) → fewer chunks → fewer LLM calls |
| More parallel throughput | Increase `max_concurrent_activities` in worker.py (risk: RAM pressure) |
| GPU acceleration | Set `LLM_GPU_LAYERS=35` and install CUDA + `llama-cpp-python[cuda]` |
| Reduce QA pairs | Lower `minItems`/`maxItems` in `generate_qa.py` and update prompt |
