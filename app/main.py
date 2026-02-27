"""
app/main.py – FastAPI application for Merlin offline document assistant.

Endpoints:
  POST /v1/chat/completions  – OpenAI-compatible chat endpoint
  POST /chat                 – Simplified JSON endpoint
  GET  /health               – Health check
  GET  /                     – Minimal web UI (if ui_enabled)
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.client import Message, chat_completion
from app.llm.prompting import build_messages, format_context_block, format_citation
from app.reasoning.router import route_and_retrieve

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(asctime)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Merlin – Offline Document Assistant", version="1.0.0")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    """OpenAI-compatible chat request."""
    model: str = Field(default="local-model")
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False


class SimpleChatRequest(BaseModel):
    """Simplified single-turn request."""
    query: str
    history: list[dict] = Field(default_factory=list)


class SimpleChatResponse(BaseModel):
    answer: str
    citations: list[str]
    is_triage: bool
    query_id: str


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _audit(query_id: str, query: str, chunk_ids: list[str], answer: str) -> None:
    """Append an audit record to the JSONL log file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query_id": query_id,
        "query": query,
        "chunk_ids": chunk_ids,
        "answer_length": len(answer),
    }
    try:
        Path(settings.audit_log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(settings.audit_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


# ---------------------------------------------------------------------------
# Core answer function
# ---------------------------------------------------------------------------

def _answer(query: str, history: list[dict] | None = None) -> SimpleChatResponse:
    """Retrieve context and generate an answer."""
    query_id = str(uuid.uuid4())

    results, sig = route_and_retrieve(
        query=query,
        db_path=settings.db_path,
        faiss_path=settings.faiss_path,
        faiss_map_path=settings.faiss_map_path,
        embedding_model=settings.embedding_model,
        top_k_bm25=settings.top_k_bm25,
        top_k_vector=settings.top_k_vector,
        top_k_final=settings.top_k_final,
        reranker_model=settings.reranker_model,
    )

    context = format_context_block(results, max_chars=settings.llm_context_window * 3)
    citations = [format_citation(r) for r in results]

    messages_dicts = build_messages(
        user_query=query,
        context=context,
        history=history,
        is_triage=sig.is_log,
    )
    llm_messages = [Message(role=m["role"], content=m["content"]) for m in messages_dicts]

    try:
        response = chat_completion(
            messages=llm_messages,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
        answer = response.content
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        if results:
            answer = (
                "The LLM backend is unavailable.  "
                "Here are the most relevant retrieved passages:\n\n"
                + "\n\n".join(f"{format_citation(r)}\n{r.text}" for r in results)
            )
        else:
            answer = "The LLM backend is unavailable and no relevant documents were found."

    _audit(query_id, query, [r.chunk_id for r in results], answer)

    return SimpleChatResponse(
        answer=answer,
        citations=citations,
        is_triage=sig.is_log,
        query_id=query_id,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/chat", response_model=SimpleChatResponse)
async def chat(req: SimpleChatRequest) -> SimpleChatResponse:
    """Simple single-turn chat endpoint."""
    return _answer(req.query, req.history or None)


@app.post("/v1/chat/completions")
async def openai_chat(req: ChatRequest) -> dict:
    """OpenAI-compatible /v1/chat/completions endpoint.

    Extracts the last user message as the query and passes earlier
    messages as history.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    # Find the last user message
    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")

    query = user_messages[-1].content
    history = [{"role": m.role, "content": m.content} for m in req.messages[:-1]]

    result = _answer(query, history if history else None)

    return {
        "id": f"chatcmpl-{result.query_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": settings.llm_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# ---------------------------------------------------------------------------
# Minimal Web UI
# ---------------------------------------------------------------------------

_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Merlin – Document Assistant</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  header { background: #16213e; padding: 12px 20px; border-bottom: 1px solid #0f3460; display: flex; align-items: center; gap: 10px; }
  header h1 { font-size: 1.2rem; color: #e94560; }
  header span { font-size: 0.8rem; color: #888; }
  #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
  .msg { max-width: 80%; padding: 10px 14px; border-radius: 8px; line-height: 1.5; white-space: pre-wrap; font-size: 0.9rem; }
  .user { background: #0f3460; align-self: flex-end; }
  .assistant { background: #16213e; border: 1px solid #0f3460; align-self: flex-start; }
  .citations { font-size: 0.75rem; color: #888; margin-top: 6px; border-top: 1px solid #333; padding-top: 4px; }
  .triage-badge { display: inline-block; background: #e94560; color: white; font-size: 0.65rem; padding: 1px 6px; border-radius: 10px; margin-left: 6px; vertical-align: middle; }
  #form { display: flex; gap: 8px; padding: 12px 20px; background: #16213e; border-top: 1px solid #0f3460; }
  #input { flex: 1; padding: 10px 14px; background: #0f3460; border: 1px solid #e94560; border-radius: 6px; color: #e0e0e0; font-size: 0.9rem; resize: none; height: 60px; }
  #input:focus { outline: none; border-color: #e94560; }
  button { background: #e94560; color: white; border: none; border-radius: 6px; padding: 0 20px; cursor: pointer; font-size: 0.9rem; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .spinner { display: none; align-self: flex-start; padding: 10px; color: #888; font-size: 0.85rem; }
  .spinner.visible { display: block; }
</style>
</head>
<body>
<header>
  <h1>🔮 Merlin</h1>
  <span>Offline Document Assistant</span>
</header>
<div id="chat"></div>
<div class="spinner" id="spinner">Thinking…</div>
<form id="form" onsubmit="return false;">
  <textarea id="input" placeholder="Ask a question or paste an error log…" rows="2"></textarea>
  <button id="send" type="button" onclick="sendMessage()">Send</button>
</form>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const spinner = document.getElementById('spinner');
const sendBtn = document.getElementById('send');
let history = [];

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

function addMessage(role, text, citations, isTriage) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  if (role === 'assistant') {
    if (isTriage) {
      const badge = document.createElement('span');
      badge.className = 'triage-badge';
      badge.textContent = 'TRIAGE';
      div.prepend(badge);
    }
    if (citations && citations.length) {
      const c = document.createElement('div');
      c.className = 'citations';
      c.textContent = 'Sources: ' + citations.join(' · ');
      div.appendChild(c);
    }
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function sendMessage() {
  const q = input.value.trim();
  if (!q) return;
  addMessage('user', q, null, false);
  history.push({role: 'user', content: q});
  input.value = '';
  sendBtn.disabled = true;
  spinner.classList.add('visible');
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q, history: history.slice(0, -1)})
    });
    const data = await res.json();
    addMessage('assistant', data.answer, data.citations, data.is_triage);
    history.push({role: 'assistant', content: data.answer});
  } catch(e) {
    addMessage('assistant', 'Error: ' + e.message, null, false);
  } finally {
    sendBtn.disabled = false;
    spinner.classList.remove('visible');
  }
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    if not settings.ui_enabled:
        return HTMLResponse("<h1>UI disabled</h1>", status_code=404)
    return HTMLResponse(_UI_HTML)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
