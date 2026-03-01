"""FastAPI application – Merlin offline document assistant."""
# ---------------------------------------------------------------------------
# Path bootstrap – must come before any project-relative imports so that
# running `python main.py` from *inside* the app/ directory still works.
# ---------------------------------------------------------------------------
import sys as _sys
from pathlib import Path as _Path

_project_root = _Path(__file__).resolve().parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.ingestion.ingest import ingest_directory
from app.llm.client import LLMClient, LocalLLMClient, NoLLMClient, get_llm_client
from app.llm.prompting import build_chat_messages, format_citation
from app.reasoning.router import route_and_retrieve
from config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _audit(record: Dict[str, Any]) -> None:
    """Append a JSON-lines audit record."""
    try:
        Path(settings.audit_log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(settings.audit_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Audit log write failed: %s", exc)


# ---------------------------------------------------------------------------
# Startup: auto-ingest docs/ directory
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Run document ingestion before the server starts accepting requests."""
    docs_dir = Path(settings.docs_dir)
    if docs_dir.exists():
        logger.info("Auto-ingesting documents from %s …", docs_dir)
        try:
            new_chunks = ingest_directory(
                input_dir=docs_dir,
                db_path=settings.db_path,
                faiss_path=settings.faiss_path,
                faiss_map_path=settings.faiss_map_path,
                skip_known=True,
            )
            if new_chunks:
                logger.info("Startup ingestion complete: %d new chunk(s) indexed.", new_chunks)
            else:
                logger.info("Startup ingestion: no new documents found.")
        except Exception as exc:
            logger.error("Startup ingestion failed: %s", exc)
    else:
        logger.info("docs/ directory not found – skipping startup ingestion.")
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Merlin - Offline Document Assistant", version="1.0.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    expand: bool = False


class ChatResponse(BaseModel):
    answer: str
    citations: List[str]
    is_triage: bool
    chunk_ids: List[int]


class OpenAIChatRequest(BaseModel):
    model: str = "local-model"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False


class OpenAIChatResponse(BaseModel):
    id: str = "chatcmpl-merlin"
    object: str = "chat.completion"
    created: int = 0
    model: str
    choices: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Shared retrieval + LLM logic
# ---------------------------------------------------------------------------


def _get_llm_client() -> Union[LLMClient, LocalLLMClient, NoLLMClient]:
    return get_llm_client(
        mode=settings.llm_mode,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        model_path=settings.llm_model_path,
        n_ctx=settings.llm_context_window,
    )


def _handle_query(query: str, expand: bool = False) -> ChatResponse:
    """Core query handler used by both endpoints."""
    results, is_triage = route_and_retrieve(
        query=query,
        db_path=settings.db_path,
        faiss_path=settings.faiss_path,
        faiss_map_path=settings.faiss_map_path,
    )

    messages = build_chat_messages(
        user_query=query,
        context_results=results,
        is_triage=is_triage,
        expand=expand,
        max_context_chars=settings.max_context_chars,
    )

    llm = _get_llm_client()
    try:
        answer = llm.chat(
            messages=messages,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    citations = [format_citation(r) for r in results]
    chunk_ids = [r.chunk_id for r in results]

    _audit(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "chunk_ids": chunk_ids,
            "answer": answer,
            "is_triage": is_triage,
        }
    )

    return ChatResponse(
        answer=answer,
        citations=citations,
        is_triage=is_triage,
        chunk_ids=chunk_ids,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint."""
    llm = _get_llm_client()
    return {
        "status": "ok",
        "llm_reachable": llm.health_check(),
        "db_path": settings.db_path,
        "faiss_path": settings.faiss_path,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Simple chat endpoint."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    return _handle_query(request.message, expand=request.expand)


@app.post("/v1/chat/completions")
async def openai_chat(request: OpenAIChatRequest) -> Dict[str, Any]:
    """OpenAI-compatible chat completions endpoint."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    # Extract the last user message as the query
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")

    query = user_messages[-1].content
    response = _handle_query(query)

    # Append citations to the answer
    citation_block = ""
    if response.citations:
        citation_block = "\n\n**Sources:** " + " | ".join(response.citations)

    full_answer = response.answer + citation_block

    created_ts = int(datetime.now(timezone.utc).timestamp())
    return {
        "id": "chatcmpl-merlin",
        "object": "chat.completion",
        "created": created_ts,
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": full_answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# ---------------------------------------------------------------------------
# Static UI – mounted last so API routes take priority
# ---------------------------------------------------------------------------

_static_dir = Path(__file__).parent / "ui" / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
