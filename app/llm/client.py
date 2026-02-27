"""
app/llm/client.py – HTTP client for the llama.cpp OpenAI-compatible server.

Targets the /v1/chat/completions endpoint.  All calls are made to
localhost; no external network access is required.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0  # seconds


class Message(BaseModel):
    role: str   # "system" | "user" | "assistant"
    content: str


class ChatResponse(BaseModel):
    content: str
    model: str = ""
    usage: dict = {}


def chat_completion(
    messages: list[Message],
    base_url: str,
    model: str = "local-model",
    max_tokens: int = 1024,
    temperature: float = 0.2,
    timeout: float = DEFAULT_TIMEOUT,
) -> ChatResponse:
    """Call the llama.cpp server's /v1/chat/completions endpoint.

    Parameters
    ----------
    messages:    Conversation history as a list of Message objects.
    base_url:    llama.cpp server URL, e.g. http://localhost:8080.
    model:       Model identifier (passed to the server; often ignored).
    max_tokens:  Maximum number of tokens to generate.
    temperature: Sampling temperature.
    timeout:     HTTP request timeout in seconds.
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("LLM server HTTP error %s: %s", exc.response.status_code, exc.response.text)
        raise
    except httpx.RequestError as exc:
        logger.error("LLM server connection error: %s", exc)
        raise

    choice = data["choices"][0]["message"]["content"]
    return ChatResponse(
        content=choice,
        model=data.get("model", model),
        usage=data.get("usage", {}),
    )
