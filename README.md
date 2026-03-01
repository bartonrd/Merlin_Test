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

### 1. Run `start.bat` (Windows) or `bash start.sh` (Linux / macOS)

**Windows** – double-click `start.bat` or run it from a terminal:

```bat
start.bat
```

**Linux / macOS**:

```bash
bash start.sh
```

Both scripts are fully self-contained and will, on every run:
1. Check that Python 3 is available
2. Create a `.venv` virtual environment (skipped if it already exists)
3. Install / upgrade all dependencies from `requirements.txt`
4. Install `llama-cpp-python` for local GGUF inference (`--prefer-binary` so no compiler needed)
5. Create `.env` from `.env.example` the **first time** (skipped on subsequent runs)
6. Start the Merlin server at `http://127.0.0.1:8000`

> **Tip:** After the first run a `.env` file is created in the project root.
> Open it to change settings – e.g. point `LLM_MODEL_PATH` at a different model file.

### 2. Configure an LLM (choose one)

Merlin supports three LLM modes. Set `LLM_MODE` in a `.env` file at the project root
(copy `.env.example` as a starting point):

| Mode | When to use | What to do |
|------|-------------|------------|
| `local` | **Default** – fully offline, no separate server | `llama-cpp-python` is installed automatically by `start.bat`/`start.sh`; set `LLM_MODEL_PATH` in `.env` |
| `none` | Quickest start – no model needed | Set `LLM_MODE=none` in `.env` – returns retrieved document excerpts without AI synthesis |
| `remote` | External server | Set `LLM_BASE_URL` to your running llama.cpp / Ollama / LM Studio server |

#### Option A – Local GGUF model (default, no server needed)

`start.bat` / `start.sh` automatically installs `llama-cpp-python`. Just set the model path in `.env`:

```ini
# .env  (created automatically from .env.example on first run)
LLM_MODE=local
LLM_MODEL_PATH=C:\dev\_models\mistral-7b-instruct-v0.1.Q5_K_S.gguf
```

Change `LLM_MODEL_PATH` to point at any `.gguf` file on your machine.

#### Option B – No LLM (search only)

```ini
# .env
LLM_MODE=none
```

No model required. Chat responses show the top-ranked document excerpts.

#### Option C – Remote OpenAI-compatible server

```ini
# .env
LLM_MODE=remote
LLM_BASE_URL=http://localhost:8080
```

Start any OpenAI-compatible server separately, e.g.:

```bash
./llama-server -m ./models/mistral-7b.gguf --port 8080
# or: ollama serve
```

### 2. Ingest your documents

```bash
python -m app.ingestion.ingest --input ./docs
```

This will:
- Parse all `.md`, `.txt`, `.pdf`, `.docx` files in `./docs`
- Auto-detect document type (runbook / incident / architecture / general)
- Chunk documents with type-aware strategies
- Build a SQLite FTS5 BM25 index and a FAISS vector index

### 3. Start the server

`start.bat` (Windows) and `start.sh` (Linux/macOS) handle setup **and** launch in one step.
Just run them again whenever you want to start Merlin – they are safe to run multiple times.

**Or manually (after activating the venv):**

```bash
# From the project root
python main.py

# With options (use --host 0.0.0.0 to expose on the local network)
python main.py --host 127.0.0.1 --port 8000 --reload
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
