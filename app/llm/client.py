"""LLM client backends: remote HTTP, local llama-cpp-python, and no-LLM fallback."""
import re
from typing import Any, Dict, List, Optional, Union

import httpx


class LLMClient:
    """Client for a remote llama.cpp / OpenAI-compatible API server (LLM_MODE=remote)."""

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
                "Is the server running? "
                "Tip: set LLM_MODE=none in your .env to use Merlin without an LLM server, "
                "or LLM_MODE=local with a GGUF model file."
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


class LocalLLMClient:
    """Runs a GGUF model directly in-process via llama-cpp-python (LLM_MODE=local).

    Install the backend with:
        pip install llama-cpp-python
    """

    def __init__(self, model_path: str, n_ctx: int = 4096) -> None:
        self.model_path = model_path
        self.n_ctx = n_ctx
        self._llm: Optional[Any] = None

    def _load(self) -> Any:
        if self._llm is None:
            try:
                from llama_cpp import Llama  # type: ignore[import]
            except ImportError as exc:
                raise RuntimeError(
                    "llama-cpp-python is not installed. "
                    "Run: pip install llama-cpp-python"
                ) from exc
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                verbose=False,
            )
        return self._llm

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str:
        """Run inference locally and return the assistant content."""
        llm = self._load()
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"Unexpected local LLM response structure: {response}"
            ) from exc

    def health_check(self) -> bool:
        """Return True if the model file can be loaded."""
        try:
            self._load()
            return True
        except Exception:
            return False


class NoLLMClient:
    """Fallback client that returns retrieved document excerpts without LLM synthesis.

    Use LLM_MODE=none when no LLM server or model file is available.
    The /chat and /v1/chat/completions endpoints still work and return the
    top-ranked document chunks so users can read the source material directly.
    """

    _HEADER = (
        "**No LLM configured** – showing the most relevant document excerpts below.\n"
        "Set `LLM_MODE=remote` (external server) or `LLM_MODE=local` (local GGUF model) "
        "in your `.env` file for AI-generated answers.\n\n"
        "---\n\n"
    )

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str:
        """Return the <context> block extracted from the user message."""
        user_content = next(
            (m["content"] for m in messages if m.get("role") == "user"), ""
        )
        match = re.search(r"<context>(.*?)</context>", user_content, re.DOTALL)
        context_text = match.group(1).strip() if match else user_content
        return self._HEADER + context_text

    def health_check(self) -> bool:
        return True


def get_llm_client(
    mode: str,
    base_url: str = "http://localhost:8080",
    model: str = "local-model",
    model_path: str = "",
    n_ctx: int = 4096,
) -> Union[LLMClient, LocalLLMClient, NoLLMClient]:
    """Factory: return the appropriate LLM client for the configured mode.

    Args:
        mode:       "remote", "local", or "none"
        base_url:   HTTP base URL for the remote server (mode=remote)
        model:      Model name to pass to the remote server (mode=remote)
        model_path: Path to a .gguf file (mode=local)
        n_ctx:      Context window size (mode=local)
    """
    if mode == "local":
        if not model_path:
            raise RuntimeError(
                "LLM_MODE=local requires LLM_MODEL_PATH to be set to a .gguf file path. "
                "See .env.example for details."
            )
        return LocalLLMClient(model_path=model_path, n_ctx=n_ctx)
    if mode == "none":
        return NoLLMClient()
    # Default: remote
    return LLMClient(base_url=base_url, model=model)

