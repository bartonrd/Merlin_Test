"""HTTP client for llama.cpp / OpenAI-compatible LLM server."""
from typing import Any, Dict, List, Optional

import httpx


class LLMClient:
    """Client for an llama.cpp OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str:
        """Send a chat completion request and return the assistant content."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to LLM server at {self.base_url}. "
                "Is the server running?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"LLM server returned HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"Unexpected LLM response structure: {data}"
            ) from exc

    def health_check(self) -> bool:
        """Return True if the LLM server is reachable."""
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                timeout=5.0,
            )
            return response.status_code < 500
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
