# ⚡ Merlin C# – Power System Apps Agent

A complete C# / ASP.NET Core port of the Merlin Power System Apps Agent.  
It exposes the same REST API as the Python version and serves the same chat UI.

---

## Architecture

| Layer | Python original | C# equivalent |
|---|---|---|
| Web framework | FastAPI | ASP.NET Core Web API |
| Configuration | pydantic-settings | `IOptions<MerlinSettings>` / `appsettings.json` |
| BM25 search | SQLite FTS5 (via Python sqlite3) | SQLite FTS5 (via Microsoft.Data.Sqlite) |
| Vector search | FAISS IndexFlatIP | Pure C# cosine-similarity `VectorStore` |
| Embeddings | sentence-transformers | Remote HTTP `/v1/embeddings` endpoint |
| LLM client | httpx → OpenAI-compatible API | `HttpClient` → OpenAI-compatible API |
| PDF loading | pdfplumber | PdfPig |
| DOCX loading | python-docx | DocumentFormat.OpenXml |
| Static UI | FastAPI StaticFiles | ASP.NET Core `UseStaticFiles` |

---

## Quick Start

### Windows

```bat
cd Merlin.CSharp
start.bat
```

### Linux / macOS

```bash
cd Merlin.CSharp
bash start.sh
```

Both scripts will:
1. Check that .NET 8+ SDK is installed
2. Create `data/` and `docs/` directories
3. Copy `appsettings.json` to `appsettings.Local.json` on first run
4. Start Merlin at `http://127.0.0.1:8000`

---

## Requirements

- [.NET 8 SDK](https://dotnet.microsoft.com/download) (or later)
- An **OpenAI-compatible LLM server** (e.g. [llama.cpp](https://github.com/ggerganov/llama.cpp), [Ollama](https://ollama.ai), LM Studio)
- An **OpenAI-compatible embedding server** (e.g. Ollama with `ollama pull all-minilm`)

> **Quickest start (no AI):** set `"LlmMode": "none"` and `"EmbedMode": "none"` in `appsettings.json` to use BM25-only search without any model.

---

## Configuration

Edit `Merlin.CSharp/src/Merlin/appsettings.json` (or create `appsettings.Local.json`):

```json
{
  "Merlin": {
    "LlmMode":    "remote",
    "LlmBaseUrl": "http://localhost:8080",
    "LlmModel":   "local-model",

    "EmbedMode":    "remote",
    "EmbedBaseUrl": "http://localhost:11434",
    "EmbedModel":   "all-minilm",

    "DocsDir":    "./docs",
    "DbPath":     "./data/db.sqlite",
    "VectorStorePath": "./data/vectors.bin"
  }
}
```

| Key | Default | Description |
|---|---|---|
| `LlmMode` | `remote` | `remote` (HTTP server) or `none` (no LLM, excerpts only) |
| `LlmBaseUrl` | `http://localhost:8080` | Base URL of the OpenAI-compatible LLM server |
| `LlmModel` | `local-model` | Model name sent in the request body |
| `EmbedMode` | `remote` | `remote` (HTTP embedding API) or `none` (BM25-only) |
| `EmbedBaseUrl` | `http://localhost:11434` | Ollama / embedding server base URL |
| `EmbedModel` | `all-minilm` | Embedding model name (Ollama: `all-minilm`) |
| `TopKBm25` | `10` | BM25 candidates per query |
| `TopKVector` | `10` | Vector search candidates per query |
| `TopKFinal` | `5` | Final results after score fusion |
| `MinVectorScore` | `0.3` | Minimum cosine similarity threshold |
| `DbPath` | `./data/db.sqlite` | SQLite database path |
| `VectorStorePath` | `./data/vectors.bin` | Vector store binary file path |
| `DocsDir` | `./docs` | Directory to watch for documents |
| `AuditLogPath` | `./data/audit.log` | JSON-lines audit log |

---

## Embedding Providers

### Option A – Ollama (recommended for offline use)

```bash
ollama pull all-minilm
ollama serve              # starts on http://localhost:11434
```

```json
"EmbedMode":    "remote",
"EmbedBaseUrl": "http://localhost:11434",
"EmbedModel":   "all-minilm"
```

### Option B – No embeddings (BM25-only)

```json
"EmbedMode": "none"
```

Vector search is disabled; only SQLite FTS5 BM25 is used.

---

## Document Ingestion

Drop `.txt`, `.md`, `.pdf`, or `.docx` files into the `docs/` directory.  
Merlin automatically indexes new documents on every startup.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Chat endpoint (`{message, expand?}`) |
| `POST` | `/generate` | Integration endpoint (`{prompt, system_prompt?, temperature?}`) |
| `POST` | `/v1/chat/completions` | OpenAI-compatible completions |
| `GET` | `/` | Chat UI |

---

## Running Tests

```bash
cd Merlin.CSharp
dotnet test
```

---

## Project Structure

```
Merlin.CSharp/
├── Merlin.sln
├── start.bat / start.sh
├── src/Merlin/
│   ├── Program.cs                   # DI wiring + app builder
│   ├── appsettings.json             # Default configuration
│   ├── Configuration/
│   │   └── MerlinSettings.cs        # Typed settings (mirrors config.py)
│   ├── Models/
│   │   ├── Chunk.cs                 # Document chunk
│   │   ├── SearchResult.cs          # Retrieval result
│   │   ├── ApiModels.cs             # Request / response DTOs
│   │   └── LogSignature.cs          # Parsed error-log signature
│   ├── Ingestion/
│   │   ├── DocumentLoaders.cs       # TXT / MD / PDF / DOCX loaders
│   │   ├── DocumentChunker.cs       # Type-aware chunking (mirrors chunking.py)
│   │   ├── IEmbeddingService.cs     # Embedding abstraction
│   │   ├── EmbeddingService.cs      # Remote HTTP + NoOp implementations
│   │   └── IngestionService.cs      # Orchestrates ingest pipeline
│   ├── Retrieval/
│   │   ├── VectorStore.cs           # Pure C# cosine-similarity store (replaces FAISS)
│   │   ├── Bm25SearchService.cs     # SQLite FTS5 BM25 search
│   │   ├── VectorSearchService.cs   # Vector search using VectorStore
│   │   └── HybridSearchService.cs   # Score fusion (BM25 + vector)
│   ├── Llm/
│   │   ├── ILlmClient.cs            # LLM abstraction
│   │   ├── LlmClients.cs            # RemoteLlmClient + NoLlmClient
│   │   └── PromptBuilder.cs         # Prompt building + citation formatting
│   ├── Reasoning/
│   │   ├── LogParser.cs             # Error-log / stack-trace detection
│   │   └── QueryRouter.cs           # Routing (triage vs normal)
│   ├── Services/
│   │   ├── AuditLogger.cs           # JSON-lines audit log writer
│   │   └── StartupIngestionService.cs  # IHostedService for startup ingestion
│   ├── Controllers/
│   │   └── MerlinController.cs      # REST API endpoints
│   └── wwwroot/
│       └── index.html               # Single-page chat UI
└── tests/Merlin.Tests/
    ├── ChunkerTests.cs              # Document chunking tests
    └── LogParserTests.cs            # Log parser / triage detection tests
```
