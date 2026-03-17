"""Programmatic resolver for FWF266 fatal workflow failures.

FWF266 indicates a missing Line Conductor Model in global.csv.
This module implements the deterministic resolution algorithm defined in
docs/fatal_resolution/FWF266/ReadMe.md so that exact ``global_csv_line_text``
and ``global_csv_line_number`` values can be computed and returned to the user
without relying on the LLM to perform string matching or arithmetic on the CSV.
"""
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Matches the FWF266 error code anywhere in a log line.
_FWF266_RE = re.compile(r"\bFWF266\b")

# Matches a voltage suffix like "2.9KV", "4KV", "12KV" at the end of a string.
# Captures (base_prefix, voltage_digits) separately.
_VOLTAGE_SUFFIX_RE = re.compile(r"^(.*?)(\d+(?:\.\d+)?)KV$", re.IGNORECASE)


@dataclass
class FWF266Resolution:
    """Result of a successful FWF266 resolution."""

    global_csv_line_text: str
    global_csv_line_number: int  # 0-based line index in global.csv where the new row is inserted (= reference_row_index + 1)
    confidence: float
    notes: str


def is_fwf266(text: str) -> bool:
    """Return True if *text* contains an FWF266 error code."""
    return bool(_FWF266_RE.search(text))


def _parse_conductor_group(conductor_group: str) -> Tuple[Optional[str], Optional[float]]:
    """Split a Conductor_Group value into (base_prefix, voltage_kv).

    Examples::

        'OH_653_A_2PH_653_A_N_2.9KV'  -> ('OH_653_A_2PH_653_A_N_', 2.9)
        'OH_653_A_2PH_653_A_N_4KV'    -> ('OH_653_A_2PH_653_A_N_', 4.0)
        'OH_653_A_2PH_653_A_N_UNKNOWN' -> (None, None)

    Returns ``(None, None)`` when the voltage suffix cannot be parsed.
    """
    m = _VOLTAGE_SUFFIX_RE.match(conductor_group.strip())
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def _format_voltage(voltage_kv: float) -> str:
    """Render a voltage value as a compact string (no trailing zeros)."""
    if voltage_kv == int(voltage_kv):
        return str(int(voltage_kv))
    return str(voltage_kv)


def _extract_error_column(log_line: str, col_index: int) -> Optional[str]:
    """Return the value at *col_index* (0-based) from a comma-delimited log line."""
    parts = log_line.strip().split(",")
    if len(parts) <= col_index:
        return None
    return parts[col_index].strip()


def resolve(
    error_log_line: str,
    global_csv_path: str,
) -> Optional[FWF266Resolution]:
    """Resolve an FWF266 error log entry to a proposed ``global.csv`` insert.

    Implements the five-step algorithm from
    ``docs/fatal_resolution/FWF266/ReadMe.md``:

    1. Filter global.csv by ``Model_Type == "Conductor_Model"``.
    2. Parse ``Error_Column_7`` (index 6, 0-based) for the target conductor
       group and voltage.
    3. Retain only records whose ``Conductor_Group`` starts with the extracted
       base prefix.
    4. Select the record whose voltage is closest to the target (higher voltage
       wins ties).
    5. Build and return a proposed new record with the ``Conductor_ID``
       suffixed by ``"a"`` and the ``Conductor_Group`` updated to the target
       voltage.

    Returns ``None`` when any termination condition from the ReadMe is met
    (missing file, unparseable voltage, no prefix match, etc.).
    """
    global_path = Path(global_csv_path)
    if not global_path.exists():
        return None

    # Step 2: Extract target Conductor_Group from column index 6.
    target_cg = _extract_error_column(error_log_line, 6)
    if not target_cg:
        return None

    base_prefix, target_voltage = _parse_conductor_group(target_cg)
    if base_prefix is None or target_voltage is None:
        return None

    # Step 1 + 3: Scan global.csv for Conductor_Model records that share the
    # base prefix and have a parseable voltage.
    candidates: List[Tuple[int, List[str], float]] = []  # (line_idx, row, voltage)

    with global_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        for line_idx, row in enumerate(reader):
            if not row or row[0] != "Conductor_Model":
                continue
            # row[1] == "0" is the column-header row for this model type; skip it.
            if len(row) < 4 or row[1] == "0":
                continue
            conductor_group = row[3]
            if not conductor_group.startswith(base_prefix):
                continue
            _, voltage = _parse_conductor_group(conductor_group)
            if voltage is None:
                continue
            candidates.append((line_idx, row, voltage))

    if not candidates:
        return None

    # Step 4: Find the candidate with the smallest |voltage - target|.
    # Ties are broken by selecting the *higher* voltage.
    best_line_idx, best_row, best_voltage = min(
        candidates,
        key=lambda x: (abs(x[2] - target_voltage), -x[2]),
    )

    # Step 5: Build the proposed new record.
    proposed_id = best_row[2] + "a"
    proposed_cg = base_prefix + _format_voltage(target_voltage) + "KV"

    proposed_row = list(best_row)
    proposed_row[2] = proposed_id
    proposed_row[3] = proposed_cg

    # Serialize back to a single CSV line without a trailing newline.
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(proposed_row)
    proposed_line_text = buf.getvalue()

    insert_at = best_line_idx + 1

    notes = (
        f"Closest reference at index {best_line_idx} "
        f"({_format_voltage(best_voltage)}KV); "
        f"updated Conductor_Group to {_format_voltage(target_voltage)}KV; "
        f"appended 'a' to Conductor_ID"
    )

    return FWF266Resolution(
        global_csv_line_text=proposed_line_text,
        global_csv_line_number=insert_at,
        confidence=0.92,
        notes=notes,
    )
