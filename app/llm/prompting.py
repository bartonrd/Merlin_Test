"""
app/llm/prompting.py – System prompt, citation formatting, and context assembly.

Citation format: [doc_title §section:chunk_index] (path)
"""
from __future__ import annotations

from app.retrieval.bm25 import SearchResult

SYSTEM_PROMPT = """\
You are Merlin, an offline document assistant for internal engineering teams.
Your purpose is to answer questions about internal systems, runbooks, architecture,
and incident history using ONLY the provided context documents.

RULES:
1. Base every factual claim on the provided context.  Format citations as
   [Title §Section:N] where N is the chunk index, e.g. [DB Runbook §Procedure:2].
2. If the answer cannot be found in the context, state: "Inference: <your reasoning>"
   and make your uncertainty explicit.  NEVER fabricate runbook steps.
3. Be detailed but concise.  Use bullet points and numbered lists where appropriate.
4. When given an error log or stack trace (triage mode), respond with:
   ## Likely Cause (ranked, max 3)
   ## Safest Next Steps (read-only first, then reversible, then risky)
   ## Verification Steps
   ## If Still Failing: Evidence to Capture / When to Escalate
   ## Confidence: High/Med/Low — <brief reason>
5. If the user asks "expand" or "more detail", provide a longer explanation
   while still citing sources.
"""

TRIAGE_INSTRUCTION = """\
The user has provided an error log or stack trace.  Apply triage mode:
analyse the signals, compare to incident history and runbooks in the context,
and respond using the triage template defined in your system prompt.
"""


def format_citation(result: SearchResult) -> str:
    """Return a short inline citation string for a search result."""
    section_part = f" §{result.section}" if result.section else ""
    return f"[{result.title}{section_part}:{result.chunk_index}]"


def format_context_block(results: list[SearchResult], max_chars: int = 6000) -> str:
    """Assemble the context block to inject into the prompt.

    Chunks are included in ranked order; the block is truncated to
    *max_chars* characters, cutting whole chunks to avoid mid-sentence breaks.
    Higher-ranked chunks appear first so truncation drops the weakest evidence.
    """
    lines: list[str] = []
    total = 0
    for r in results:
        citation = format_citation(r)
        block = f"--- {citation} (path: {r.path}) ---\n{r.text}\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)
    return "\n".join(lines)


def build_messages(
    user_query: str,
    context: str,
    history: list[dict] | None = None,
    is_triage: bool = False,
) -> list[dict]:
    """Build the messages list for the chat completion API.

    Parameters
    ----------
    user_query: The user's current question or log snippet.
    context:    Assembled context string from ``format_context_block``.
    history:    Optional previous turns as [{"role": ..., "content": ...}].
    is_triage:  If True, add the triage instruction to the user message.
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    user_content_parts = []
    if context:
        user_content_parts.append(f"<context>\n{context}\n</context>")
    if is_triage:
        user_content_parts.append(TRIAGE_INSTRUCTION)
    user_content_parts.append(user_query)

    messages.append({"role": "user", "content": "\n\n".join(user_content_parts)})
    return messages
