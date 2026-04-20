# SDG Temporal: Markdown processing pipeline

A high-performance, resilient pipeline for processing Markdown files into Knowledge Base (KB) entries and Q&A pairs using **Temporal** and local **LLMs** (llama-cpp).

## 🚀 Overview

This system automates the ingestion of documentation:
1.  **Parse**: Cleans and extracts metadata from Markdown.
2.  **Chunk**: Splits content into semantic sections.
3.  **Analyze (Parallel)**: Uses a local LLM to generate KB summaries and Q&A pairs for each chunk in parallel.
4.  **Store**: Persists results into a PostgreSQL database with full idempotency.

---

## 🏗 Architecture

-   **Orchestrator**: [Temporal](https://temporal.io/) (Handles retries, state, and parallel execution).
-   **Processor**: Python workers running `llama-cpp-python`.
-   **Database**: PostgreSQL with JSONB support for structured knowledge.
-   **LLM**: Any GGUF-compatible model (e.g., Mistral, Llama 3).

---

## 🛠 Setup

### 1. Prerequisites
-   Docker and Docker Compose.
-   A GGUF model file (e.g., `mistral-7b-v0.1.Q4_K_M.gguf`).

### 2. Prepare Models
Create a `models` directory and place your `.gguf` file inside.
```bash
mkdir models
# Place your model in ./models/model.gguf
```

### 3. Environment Config
The system reads from `.env`. Ensure the `LLM_MODEL_PATH` matches your model filename.
```bash
cp .env.example .env  # If example exists, otherwise see .env
```

---

## 🚦 How to Run (Hybrid Local Setup)

To maximize performance (especially if using GPU acceleration for the LLM), the infrastructure runs in Docker, while the actual Python Worker runs natively on your machine.

### 1. Start Infrastructure
Start the Temporal server and PostgreSQL database in the background:
```bash
docker-compose -f docker/docker-compose.yml up -d postgres temporal temporal-ui
```

### 2. Install Local Dependencies
Create a virtual environment and install the necessary Python packages, including the local LLM engine:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install llama-cpp-python
```

### 3. Run the Worker
Point the environment to your downloaded GGUF model and start the Temporal worker:
```bash
export LLM_MODEL_PATH="./models/LFM2.5-1.2B-Instruct-Q8_0.gguf"
python3 -m app.workers.worker
```

---

## ⚡ Triggering Workflows

Once the worker is running, you can ingest files using the CLI tool:

### Process a single file:
```bash
python3 -m app.main --file ./data/sample.md
```

### Process an entire directory:
```bash
python3 -m app.main --dir ./data/docs/
```

## ⚡ Execution Commands

### A. Ingest Single File
```bash
python3 -m app.main --file ./data/markdown/sample.md
```

### B. Ingest Entire Directory (Batch)
```bash
python3 -m app.main --dir ./data/markdown/
```

### C. Export Results to Text
```bash
python3 scripts/export_db.py
```

---

## 🔍 Monitoring & DB Checks

### Temporal Dashboard
👉 **[http://localhost:8080](http://localhost:8080)**

### Database Queries (via Docker)
```bash
# Check Documents
docker exec -it md_postgres psql -U user -d md_pipeline -c "SELECT id, title, created_at FROM documents;"

# Check Q&A Density
docker exec -it md_postgres psql -U user -d md_pipeline -c "SELECT count(*) FROM qa_pairs;"

# Clean Database (CAUTION)
docker exec md_postgres psql -U user -d md_pipeline -c "TRUNCATE documents CASCADE;"
```

---

> 📚 **Technical Deep Dive**: For architecture details, chunking logic, and LLM tuning instructions, see [INFO.md](INFO.md).
