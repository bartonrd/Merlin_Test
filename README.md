# ⚡ Merlin – Offline Document Assistant

Merlin is a self-hosted, offline-first document assistant (ChatGPT-style) that answers questions and triages incidents using your own internal runbooks, architecture documents, and incident history — powered by a local LLM (e.g. llama.cpp) and hybrid BM25 + FAISS vector search.

---

## Features

| Capability | Detail |
|---|---|
| **Document ingestion** | `.txt`, `.md`, `.pdf`, `.docx` → SQLite FTS5 + FAISS index |
| **Hybrid search** | BM25 (SQLite FTS5) + Semantic (sentence-transformers + FAISS) |
| **Smart chunking** | Type-aware strategies for runbooks, incidents, architecture docs |
| **Triage mode** | Auto-detects error logs / stack traces → structured SRE triage output |
| **Citation tracking** | Every answer cites source documents and sections |
| **Audit logging** | All queries and answers appended as JSON-lines |
| **OpenAI-compatible API** | Drop-in `/v1/chat/completions` endpoint |
| **Built-in UI** | Dark-themed single-page chat interface with expand & citations |
| **Fully offline** | No external API calls; runs on your own hardware |

---

## Quick Start

### 1. Install dependencies

**Windows** – double-click `setup_requirements.bat` or run it from a terminal:

```bat
setup_requirements.bat
```

**Linux / macOS** – run the shell script:

```bash
bash setup_requirements.sh
```

Both scripts will:
- Check that Python 3 is available
- Create a `.venv` virtual environment in the project root (skipped if it already exists)
- Upgrade pip and install everything in `requirements.txt`
- Print the next steps when finished

If you prefer to do it manually:

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bat
:: Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start a local LLM server

Any OpenAI-compatible server works (llama.cpp, LM Studio, Ollama with the OpenAI compat layer):

```bash
# Example with llama.cpp server
./llama-server -m ./models/mistral-7b.gguf --port 8080
```

### 3. Ingest your documents

```bash
python -m app.ingestion.ingest --input ./docs
```

This will:
- Parse all `.md`, `.txt`, `.pdf`, `.docx` files in `./docs`
- Auto-detect document type (runbook / incident / architecture / general)
- Chunk documents with type-aware strategies
- Build a SQLite FTS5 BM25 index and a FAISS vector index

### 4. Start the server

**Option A – simple script (Windows-friendly):**

```bash
# From the project root
python main.py

# With options (use --host 0.0.0.0 to expose on the local network)
python main.py --host 127.0.0.1 --port 8000 --reload
```

**Option B – uvicorn directly:**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
.
├── config.py                   # Pydantic-settings configuration
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI application
│   ├── ingestion/
│   │   ├── loaders.py          # File loaders (txt, md, pdf, docx)
│   │   ├── chunking.py         # Smart type-aware chunking
│   │   ├── embed.py            # Sentence-transformer embeddings
│   │   └── ingest.py           # CLI ingest script
│   ├── retrieval/
│   │   ├── bm25.py             # SQLite FTS5 BM25 search
│   │   ├── faiss_store.py      # FAISS vector search
│   │   └── hybrid.py           # Score fusion + optional reranking
│   ├── llm/
│   │   ├── client.py           # LLM HTTP client (OpenAI-compatible)
│   │   └── prompting.py        # Prompt building + citation formatting
│   ├── reasoning/
│   │   ├── log_parser.py       # Error log / stack trace detection
│   │   └── router.py           # Query routing (triage vs normal)
│   └── ui/static/
│       └── index.html          # Single-page chat UI
├── docs/                       # Sample documents
├── data/                       # Generated indexes and DB (gitignored)
└── tests/
    ├── test_chunking.py
    └── test_log_parser.py
```

---

## Configuration

All settings can be overridden via environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8080` | LLM server URL |
| `LLM_MODEL` | `local-model` | Model name to pass to the API |
| `LLM_MAX_TOKENS` | `2048` | Max tokens per response |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `EMBED_DEVICE` | `cpu` | `cpu` or `cuda` |
| `TOP_K_BM25` | `10` | BM25 candidates |
| `TOP_K_VECTOR` | `10` | Vector search candidates |
| `TOP_K_FINAL` | `5` | Final results after fusion |
| `RERANKER_ENABLED` | `false` | Enable cross-encoder reranking |
| `DB_PATH` | `./data/db.sqlite` | SQLite database path |
| `FAISS_PATH` | `./data/index.faiss` | FAISS index path |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (LLM reachability) |
| `POST` | `/chat` | Simple chat (`{message, conversation_id?, expand?}`) |
| `POST` | `/v1/chat/completions` | OpenAI-compatible completions |
| `GET` | `/` | Chat UI (served from `app/ui/static/`) |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Adding Documents

Drop any `.md`, `.txt`, `.pdf`, or `.docx` files into `./docs/` (or any directory) and re-run the ingest script:

```bash
python -m app.ingestion.ingest --input ./docs --clear
```

The `--clear` flag drops and rebuilds the index from scratch.

---

## Triage Mode

When you paste an error log or stack trace, Merlin automatically switches to **Triage Mode** and returns a structured SRE-style response:

- **Likely Causes** (ranked)
- **Safest Next Steps** (read-only → reversible → risky)
- **Verification Steps**
- **If Still Failing**
- **Confidence level with reasoning**

Triage queries search incident history and runbooks first, then fall back to architecture docs.
