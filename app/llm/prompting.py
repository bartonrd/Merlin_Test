"""Prompt-building utilities for the document assistant."""
from typing import Dict, List, Optional

from app.retrieval.bm25 import SearchResult

SYSTEM_PROMPT = """You are an expert internal document assistant and incident triage specialist.
You have access to internal runbooks, architecture documents, and incident history.

RULES:
1. Always cite sources using format: [doc_title §section:chunk_N]
2. If information comes from documents, state it as fact with citation.
3. If you are inferring or the answer is not in the documents, label it as [Inference] and explain your reasoning and uncertainty.
4. Never fabricate runbook steps or incident details.
5. Be detailed but concise. Default to concise answers unless asked to expand.
6. Structure your answers clearly.
"""

TRIAGE_SYSTEM_PROMPT = """You are an expert SRE and incident triage specialist.
You are analyzing error logs or stack traces and comparing them to known incidents and runbooks.

RULES (SAME AS ABOVE, PLUS):
7. Use the "Triage Mode" output format:
   ## Likely Cause (max 3, ranked)
   ## Safest Next Steps (read-only → reversible → risky)
   ## Verification Steps
   ## If Still Failing
   ## Confidence: High/Med/Low [reason]
8. Always cite similar incidents and runbooks with format: [doc_title §section:chunk_N]
9. Never guess at infrastructure specifics not found in documents.
"""

FWF266_SYSTEM_PROMPT = """You are Merlin, a power-system configuration assistant.
You have been provided with a <computed> block containing the exact, programmatically
derived resolution for an FWF266 fatal workflow failure.

RULES:
1. Report the values from the <computed> block VERBATIM – do not alter them.
2. Present the action_payload JSON exactly as shown in the <computed> block.
3. Briefly explain the resolution (which reference row was used, why).
4. Do not invent or modify any CSV field values.
5. If the <computed> block contains "no_action: true", report that no action is
   required and explain the reason given.
"""

EXPAND_INSTRUCTION = (
    "\n\nThe user has asked you to expand on your previous answer. "
    "Provide more detail, additional context, and deeper explanation."
)


def format_citation(result: SearchResult) -> str:
    """Format a chunk as a citation string."""
    return f"[{result.title} §{result.section}:chunk_{result.chunk_index}]"


def format_context(results: List[SearchResult], max_chars: int = 6000) -> str:
    """Format retrieved chunks as a context block, respecting max_chars.

    Highest-ranked results are included first; truncation happens at the end.
    """
    lines: List[str] = ["<context>"]
    total = len("<context>") + len("</context>")

    for result in results:
        header = (
            f"\n[Source: {result.title} | section: {result.section} "
            f"| chunk: {result.chunk_index} | type: {result.doc_type}]\n"
        )
        block = header + result.text.strip() + "\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    lines.append("</context>")
    return "".join(lines)


def format_fwf266_computed(
    global_csv_line_text: str,
    global_csv_line_number: int,
    confidence: float,
    notes: str,
) -> str:
    """Format the programmatically computed FWF266 resolution as a <computed> block.

    This block is injected into the user message so the LLM can report the
    exact values without having to derive them itself.
    """
    import json

    action_payload = {
        "actions": [
            {
                "action": "propose_global_csv_insert",
                "global_csv_line_text": global_csv_line_text,
                "global_csv_line_number": global_csv_line_number,
            }
        ],
        "confidence": confidence,
        "notes": notes,
    }
    payload_str = json.dumps(action_payload, indent=2)

    return (
        "<computed>\n"
        "FWF266 resolution (programmatically computed from global.csv):\n\n"
        f"global_csv_line_text: {global_csv_line_text!r}\n"
        f"global_csv_line_number: {global_csv_line_number}\n\n"
        f"action_payload:\n{payload_str}\n"
        "</computed>\n"
    )


def build_chat_messages(
    user_query: str,
    context_results: List[SearchResult],
    is_triage: bool = False,
    expand: bool = False,
    max_context_chars: int = 6000,
    system_prompt: Optional[str] = None,
    computed_block: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Build the messages list for a chat completion request."""
    if system_prompt is None:
        system_prompt = TRIAGE_SYSTEM_PROMPT if is_triage else SYSTEM_PROMPT
    context_block = format_context(context_results, max_chars=max_context_chars)

    user_content = f"{context_block}\n\n"
    if computed_block:
        user_content += computed_block + "\n"
    user_content += user_query
    if expand:
        user_content += EXPAND_INSTRUCTION

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
