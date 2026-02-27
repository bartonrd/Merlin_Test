"""
app/reasoning/log_parser.py – Detect error logs / stack traces in user input
and extract key error signatures for targeted retrieval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Heuristic patterns
# ---------------------------------------------------------------------------

# Stack trace indicators
_STACK_PATTERNS = [
    re.compile(r"\bTraceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"\bat\s+\w[\w.$]+\([\w.]+:\d+\)"),       # Java stack frame
    re.compile(r"\bException in thread\b", re.IGNORECASE),
    re.compile(r"\bFATAL\b|\bPANIC\b", re.IGNORECASE),
    re.compile(r"\bCRITICAL\b.*\bERROR\b", re.IGNORECASE),
    re.compile(r"\berror:\s+\S", re.IGNORECASE),
    re.compile(r"\bERROR\s+\d{3,}\b"),                   # HTTP error codes
    re.compile(r"\[WARN\]|\[ERROR\]|\[FATAL\]", re.IGNORECASE),
    re.compile(r"\bSegmentation fault\b", re.IGNORECASE),
    re.compile(r"\bOOM\b|\bOut of Memory\b", re.IGNORECASE),
    re.compile(r"^\s+at\s+\S+\(\S+\)", re.MULTILINE),   # indented stack frames
    re.compile(r"\bNullPointerException\b|\bNPE\b"),
    re.compile(r"E\s+\w+Error:", re.MULTILINE),          # Python pytest errors
]

# Error code patterns (HTTP codes, errno-style, custom codes)
_ERROR_CODE_RE = re.compile(
    r"\b(?:E\d{3,}|ORA-\d+|SQLSTATE\s*\d+|exit\s+code\s+\d+|"
    r"errno\s+\d+|status\s+[45]\d{2}|HTTP\s+[45]\d{2}|"
    r"code\s*[:=]\s*\d{3,})\b",
    re.IGNORECASE,
)

# Exception class names
_EXCEPTION_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception|Fault|Panic|Warning))\b"
)

# Log-level lines
_LOG_LINE_RE = re.compile(
    r"^.*(?:ERROR|WARN|FATAL|CRITICAL|PANIC).*$",
    re.MULTILINE | re.IGNORECASE,
)

# Minimum line count suggesting a multi-line log (not just a one-word question)
_MIN_LOG_LINES = 3


@dataclass
class LogSignature:
    """Extracted error signals from user input."""

    is_log: bool = False
    error_codes: list[str] = field(default_factory=list)
    exception_types: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    # A condensed string suitable for retrieval queries
    search_query: str = ""


def parse_log(text: str) -> LogSignature:
    """Analyse *text* and return a ``LogSignature``.

    Sets ``is_log = True`` if the text looks like an error log or stack trace.
    Extracts error codes and exception class names for use in hybrid retrieval.
    """
    sig = LogSignature()

    # Count matching heuristic signals
    signals = sum(1 for pat in _STACK_PATTERNS if pat.search(text))
    line_count = text.count("\n") + 1

    # Treat as a log if multiple signals fire, or if there are many lines
    # containing log-level markers
    log_lines = _LOG_LINE_RE.findall(text)
    if signals >= 2 or (signals >= 1 and line_count >= _MIN_LOG_LINES) or len(log_lines) >= 2:
        sig.is_log = True

    sig.error_codes = list(dict.fromkeys(m.group(0) for m in _ERROR_CODE_RE.finditer(text)))
    sig.exception_types = list(dict.fromkeys(m.group(1) for m in _EXCEPTION_RE.finditer(text)))
    sig.log_lines = log_lines[:10]  # keep first 10 matching lines

    # Build a concise search query from extracted signals
    parts: list[str] = []
    parts.extend(sig.exception_types[:3])
    parts.extend(sig.error_codes[:3])
    if not parts and sig.log_lines:
        # Fall back to first log line, stripped
        parts.append(sig.log_lines[0].strip()[:120])
    sig.search_query = " ".join(parts) if parts else text[:200]

    return sig
