# Merlin – Offline Document Assistant

Merlin is a self-hosted, **fully offline** document assistant (ChatGPT-like)
focused on referencing internal engineering documents, runbooks, architecture
documentation, and incident history.  It performs hybrid BM25 + vector
retrieval and delegates answer generation to a local LLM served by
[llama.cpp](https://github.com/ggerganov/llama.cpp).

---

## Features

| Feature | Detail |
|---|---|
| Offline | No internet access required after setup |
| Hybrid retrieval | BM25 (SQLite FTS5) + Vector (FAISS) |
| Local embeddings | `sentence-transformers` running on CPU |
| Optional reranker | Cross-encoder model (disabled by default) |
| Triage mode | Structured analysis for error logs and stack traces |
| Citations | Every factual claim is cited `[Title §Section:N]` |
| Audit log | Every query + retrieved chunks + answer logged to JSONL |
| Web UI | Minimal dark-mode chat interface |
| OpenAI-compatible API | `/v1/chat/completions` endpoint |

---

## Project Structure

```
/app
  __init__.py
  main.py               # FastAPI server
  config.py             # Pydantic settings
  ingestion/
    __init__.py
    ingest.py           # CLI ingestion pipeline
    loaders.py          # PDF / DOCX / TXT / MD extractors
    chunking.py         # Intelligent chunking
    embed.py            # Sentence-transformer embedding helper
  retrieval/
    __init__.py
    bm25.py             # SQLite FTS5 BM25 search
    faiss_store.py      # FAISS vector search
    hybrid.py           # Hybrid merge + optional reranker
  llm/
    __init__.py
    client.py           # llama.cpp HTTP client
    prompting.py        # System prompt + citation formatting
  reasoning/
    __init__.py
    log_parser.py       # Error log detection & signature extraction
    router.py           # Query routing logic
/tests
  test_chunking.py
  test_log_parser.py
/docs                   # Sample documents (runbooks, incidents, architecture)
requirements.txt
config.yaml             # Example configuration
README.md
```

---

## Prerequisites

1. **Python 3.11+**
2. **llama.cpp server** running locally.  Start it with a GGUF model:
   ```bash
   ./llama-server -m ./models/mistral-7b-instruct.Q4_K_M.gguf \
     --host 0.0.0.0 --port 8080 --ctx-size 4096
   ```
3. *(Optional)* A GPU for faster inference; the system works on CPU.

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-org/merlin.git
cd merlin

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit the config (adjust paths as needed)
cp config.yaml config.yaml  # already provided; edit as needed
```

For PDF support (optional):
```bash
pip install pdfplumber
```

For DOCX support (optional, included in requirements):
```bash
pip install python-docx
```

To pre-download the embedding model for offline use:
```python
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")  # downloads to ~/.cache/
```

---

## Configuration

Edit `config.yaml` (or set `MERLIN_*` environment variables):

```yaml
llm_base_url: "http://localhost:8080"   # llama.cpp server
embedding_model: "all-MiniLM-L6-v2"    # offline embedding model
reranker_model: null                    # set to a cross-encoder to enable
db_path: "./data/db.sqlite"
faiss_path: "./data/index.faiss"
docs_dir: "./docs"
top_k_bm25: 10
top_k_vector: 10
top_k_final: 5
audit_log_path: "./data/audit.jsonl"
```

---

## Ingestion

Run the ingestion pipeline to index your documents:

```bash
# Index the sample docs folder
python -m app.ingestion.ingest --input ./docs --db ./data/db.sqlite --faiss ./data/index.faiss

# Index multiple folders
python -m app.ingestion.ingest \
  --input ./docs/runbooks ./docs/incidents ./docs/architecture \
  --db ./data/db.sqlite \
  --faiss ./data/index.faiss

# Force all documents to a specific type
python -m app.ingestion.ingest \
  --input ./incidents \
  --db ./data/db.sqlite \
  --faiss ./data/index.faiss \
  --doc-type incident
```

### Document type auto-detection

| Keywords in path/title | Detected type |
|---|---|
| runbook, sop, playbook, procedure | `runbook` |
| incident, postmortem, outage, pagerduty | `incident` |
| architecture, arch, design, adr | `architecture` |
| (anything else) | `general` |

### Chunking strategies

| Doc type | Strategy |
|---|---|
| `runbook` | Split by Symptoms / Cause / Procedure / Verification / Rollback headings |
| `incident` | Split by What Happened / Signals / Root Cause / Fix / Prevention headings |
| `architecture` / `general` | Split by Markdown `#` headings, then by size (≤1200 chars) |

---

## Running the Server

```bash
python -m app.main
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open your browser at **http://localhost:8000** for the web UI.

---

## API Reference

### `POST /chat`

Simple chat endpoint.

```json
{
  "query": "What should I do if pgbouncer shows cl_waiting > 100?",
  "history": []
}
```

Response:
```json
{
  "answer": "...",
  "citations": ["[DB Runbook §Procedure:2]", "..."],
  "is_triage": false,
  "query_id": "uuid"
}
```

### `POST /v1/chat/completions`

OpenAI-compatible endpoint.  Drop-in replacement for `openai` Python
client by pointing `base_url` at `http://localhost:8000/v1`.

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")
resp = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": "Explain the PostgreSQL CPU runbook."}]
)
print(resp.choices[0].message.content)
```

### `GET /health`

Returns `{"status": "ok", "ts": "..."}`.

---

## Triage Mode

When the input contains an error log or stack trace, Merlin automatically
switches to **Triage Mode** and responds with a structured template:

```
## Likely Cause (ranked, max 3)
## Safest Next Steps
## Verification Steps
## If Still Failing: Evidence to Capture / When to Escalate
## Confidence: High/Med/Low — <reason>
```

Example triage query:
```
java.lang.OutOfMemoryError: Java heap space
  at com.company.pipeline.transform.DataTransformer.process(DataTransformer.java:142)
```

---

## Web UI

The minimal dark-mode UI is served at `http://localhost:8000/`.

- Press **Enter** to send (Shift+Enter for newline)
- Triage responses are marked with a red `TRIAGE` badge
- Source citations appear below each assistant message

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Audit Log

Every query is appended to `./data/audit.jsonl`:

```json
{
  "ts": "2024-03-12T14:23:01.000Z",
  "query_id": "uuid",
  "query": "...",
  "chunk_ids": ["uuid1", "uuid2"],
  "answer_length": 512
}
```

---

## Offline Model Setup

To ensure fully offline operation, pre-download models before
disconnecting from the network:

```bash
# Embedding model (downloads to HuggingFace cache)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Optional reranker
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# LLM: download GGUF model manually and pass to llama-server
```

---

## Adding a Reranker

In `config.yaml`:
```yaml
reranker_model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

The reranker runs on CPU and is applied after hybrid search, before
context is assembled.

---

## Security Notes

- No outbound network calls are made after setup.
- The audit log records queries and chunk IDs but **not** the full
  retrieved text (to limit log size).
- No authentication is included — deploy behind a VPN or firewall.
