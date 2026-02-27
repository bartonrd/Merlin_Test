"""Heuristic detection and parsing of error logs / stack traces."""
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class LogSignature:
    error_codes: List[str] = field(default_factory=list)
    exception_types: List[str] = field(default_factory=list)
    stack_trace_lines: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    is_log: bool = False


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_PYTHON_TB = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)
_JAVA_FRAME = re.compile(r"^\s+at\s+[\w.$<>]+\(", re.MULTILINE)
_JS_FRAME = re.compile(r"^\s+at\s+.+:\d+:\d+", re.MULTILINE)
_EXCEPTION_LINE = re.compile(
    r"(Exception|Error|FATAL|CRITICAL|Traceback|Caused by)[\s:]",
    re.IGNORECASE,
)
_HTTP_5XX = re.compile(r"\bHTTP[/ ]+5\d{2}\b", re.IGNORECASE)
_HTTP_4XX = re.compile(r"\bHTTP[/ ]+4\d{2}\b", re.IGNORECASE)
_ERROR_CODE = re.compile(
    r"\b(E\d{4,}|ORA-\d+|SQLSTATE\[\d+\]|errno\s*\d+|code\s*[:=]\s*\d{3,})\b",
    re.IGNORECASE,
)
_LOG_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|\[\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_PIPE_BRACKET_LINE = re.compile(r"[\[\|]{1}.{10,}[\]\|]{1}")


def is_error_log(text: str) -> bool:
    """Detect whether *text* looks like an error log or stack trace.

    Heuristics (any 1 strong signal OR 2+ weak signals triggers True):
    - Python Traceback header
    - Java/JS stack frame lines (at com.example...)
    - Exception:/Error:/FATAL:/CRITICAL: keywords
    - HTTP 5xx error codes
    - Oracle/DB error codes (ORA-XXXXX, E0XXXX)
    - Log timestamps on multiple lines
    - Log-style pipe/bracket patterns on multiple lines
    """
    strong = [
        bool(_PYTHON_TB.search(text)),
        bool(_JAVA_FRAME.search(text)),
        bool(_JS_FRAME.search(text)),
    ]
    if any(strong):
        return True

    weak_score = 0
    weak_score += 1 if _EXCEPTION_LINE.search(text) else 0
    weak_score += 1 if _HTTP_5XX.search(text) else 0
    weak_score += 1 if _ERROR_CODE.search(text) else 0

    ts_matches = _LOG_TIMESTAMP.findall(text)
    weak_score += 1 if len(ts_matches) >= 2 else 0

    bracket_matches = _PIPE_BRACKET_LINE.findall(text)
    weak_score += 1 if len(bracket_matches) >= 2 else 0

    return weak_score >= 2


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------

_EXCEPTION_TYPE_RE = re.compile(
    r"^(?:\s+Caused by:\s+)?([A-Za-z][\w.]*(?:Exception|Error|Fault|Panic))\b",
    re.MULTILINE,
)
_STACK_FRAME_RE = re.compile(r"^\s+(?:at\s+.+|File\s+\".+\",\s+line\s+\d+)", re.MULTILINE)
_ERROR_MSG_RE = re.compile(
    r"(Exception|Error|FATAL|CRITICAL)[:\s]+(.{10,120})",
    re.IGNORECASE,
)


def parse_log_signature(text: str) -> LogSignature:
    """Extract a structured signature from an error log for improved search."""
    sig = LogSignature(is_log=is_error_log(text))

    # Error codes
    sig.error_codes = list({m.group(0) for m in _ERROR_CODE.finditer(text)})

    # HTTP codes
    http_matches = re.findall(r"\bHTTP[/ ]+(\d{3})\b", text, re.IGNORECASE)
    sig.error_codes.extend([f"HTTP_{c}" for c in http_matches])
    sig.error_codes = list(dict.fromkeys(sig.error_codes))  # dedup preserving order

    # Exception types
    sig.exception_types = list(
        dict.fromkeys(m.group(1) for m in _EXCEPTION_TYPE_RE.finditer(text))
    )

    # Stack trace lines
    sig.stack_trace_lines = _STACK_FRAME_RE.findall(text)[:10]

    # Error messages
    sig.error_messages = [
        m.group(2).strip() for m in _ERROR_MSG_RE.finditer(text)
    ][:5]

    return sig


def build_search_query(original_query: str, sig: LogSignature) -> str:
    """Build an enhanced search query from a log signature."""
    terms: List[str] = []
    terms.extend(sig.exception_types[:3])
    terms.extend(sig.error_codes[:3])
    terms.extend(sig.error_messages[:2])
    if terms:
        return " ".join(terms)
    return original_query
