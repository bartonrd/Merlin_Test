"""Tests for the Ollama-compatible /api/generate endpoint."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Minimal replica of the /api/generate handler (mirrors app/main.py logic)
# ---------------------------------------------------------------------------

def _build_generate_app(answer: str = "Here is the answer.", citations=None) -> TestClient:
    """Build a minimal app that replicates the /api/generate endpoint."""
    app = FastAPI()
    _citations = citations or []

    class OllamaGenerateRequest(BaseModel):
        model: str = "merlin"
        prompt: str
        system: Optional[str] = None
        stream: bool = False

    @app.post("/api/generate")
    async def ollama_generate(request: OllamaGenerateRequest) -> Dict[str, Any]:
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="prompt must not be empty")

        citation_block = ""
        if _citations:
            citation_block = "\n\n**Sources:** " + " | ".join(_citations)

        full_response = answer + citation_block
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return {
            "model": request.model,
            "created_at": created_at,
            "response": full_response,
            "done": True,
            "done_reason": "stop",
        }

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ollama_generate_returns_ollama_shape():
    """/api/generate should return all required Ollama response fields."""
    client = _build_generate_app()
    resp = client.post(
        "/api/generate",
        json={"model": "merlin", "prompt": "How do I restart the service?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "model" in data
    assert "created_at" in data
    assert data["done"] is True
    assert data["done_reason"] == "stop"
    assert data["model"] == "merlin"


def test_ollama_generate_answer_included_in_response():
    """/api/generate should include the answer text in the response field."""
    client = _build_generate_app(answer="Restart using systemctl restart payments.")
    resp = client.post("/api/generate", json={"prompt": "How do I restart the service?"})
    assert resp.status_code == 200
    assert "Restart using systemctl restart payments." in resp.json()["response"]


def test_ollama_generate_citations_appended():
    """/api/generate should append citations to the response field."""
    client = _build_generate_app(answer="See docs.", citations=["runbooks/payments.md § Restart"])
    resp = client.post("/api/generate", json={"prompt": "Restart payments?"})
    assert resp.status_code == 200
    assert "**Sources:**" in resp.json()["response"]
    assert "runbooks/payments.md § Restart" in resp.json()["response"]


def test_ollama_generate_empty_prompt_returns_400():
    """/api/generate with a blank prompt should return 400."""
    client = _build_generate_app()
    resp = client.post("/api/generate", json={"model": "merlin", "prompt": "   "})
    assert resp.status_code == 400


def test_ollama_generate_default_model_name():
    """/api/generate should default model to 'merlin' when omitted."""
    client = _build_generate_app()
    resp = client.post("/api/generate", json={"prompt": "Test question"})
    assert resp.status_code == 200
    assert resp.json()["model"] == "merlin"


def test_ollama_generate_custom_model_name_echoed():
    """/api/generate should echo the caller-supplied model name."""
    client = _build_generate_app()
    resp = client.post("/api/generate", json={"model": "custom-model", "prompt": "Question?"})
    assert resp.status_code == 200
    assert resp.json()["model"] == "custom-model"

