"""Prompt-building utilities for the document assistant."""
from typing import Dict, List, Optional

from app.retrieval.bm25 import SearchResult

SYSTEM_PROMPT = """You are an expert internal document assistant and incident triage specialist.
You have access to internal runbooks, architecture documents, and incident history.

RULES:
1. Cite sources inline at the end of the sentence or paragraph they support, using format: [doc_title §section:chunk_N]. Never print citations as separate list items or on their own lines.
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
1. Write a concise text explanation of the resolution:
   - State the error (missing Line Conductor Model) and affected station/device.
   - Identify the reference row used (Conductor_ID, Conductor_Group, voltage).
   - Explain WHY that reference was chosen (closest voltage match).
   - State what the proposed new row changes (Conductor_ID suffix 'a', updated voltage).
2. Do NOT output any JSON, code blocks, or action_payload JSON – this is a text-only explanation.
3. Do not invent or modify any CSV field values.
4. If the <computed> block contains "no_action: true", explain why no action is required.
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


def format_fwf266_action_only_response(
    global_csv_line_text: str,
    global_csv_line_number: int,
    confidence: float,
    notes: str,
) -> str:
    """Return ONLY the action_payload as a bare JSON code block (Action Mode).

    Used when the user explicitly requests the action_payload.  No introductory
    text is included so the response is machine-friendly and copy-pasteable.
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
    return f"```json\n{json.dumps(action_payload, indent=2)}\n```"


def format_fwf266_action_payload_block(
    global_csv_line_text: str,
    global_csv_line_number: int,
    confidence: float,
    notes: str,
) -> str:
    """Return the action_payload as a markdown JSON code block for chat display.

    This is appended programmatically to every FWF266 response so the user
    always sees both the text explanation and the machine-readable payload.
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
    return f"\n\n---\n\n**Action Payload**\n\n```json\n{payload_str}\n```"


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
