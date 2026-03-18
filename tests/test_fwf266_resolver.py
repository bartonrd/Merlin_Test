"""Tests for the FWF266 programmatic resolver."""
import csv
import json
import os
import textwrap

import pytest

from app.reasoning.fwf266_resolver import (
    FWF266Resolution,
    _format_voltage,
    _parse_conductor_group,
    is_fwf266,
    is_action_mode_request,
    resolve,
)
from app.llm.prompting import (
    format_fwf266_action_only_response,
    format_fwf266_action_payload_block,
)


# ---------------------------------------------------------------------------
# is_fwf266
# ---------------------------------------------------------------------------


def test_is_fwf266_detects_error_log():
    log = (
        "-F-,FWF266,PH382E$4115222E,Line conductor model was not found in global data.,"
        "Record name: Line Field name: CondModA,Station External Device: PH382E$4115222E,"
        "OH_653_A_2PH_653_A_N_2.9KV,,,,ALOLA,,PH382E$4115222E,ENG"
    )
    assert is_fwf266(log) is True


def test_is_fwf266_false_for_unrelated_text():
    assert is_fwf266("How do I restart the database connection pool?") is False


def test_is_fwf266_false_for_other_error_code():
    assert is_fwf266("-F-,FWF999,Some station,Some error,") is False


# ---------------------------------------------------------------------------
# is_action_mode_request
# ---------------------------------------------------------------------------


def test_is_action_mode_detects_action_payload_keyword():
    assert is_action_mode_request("give me the action_payload for FWF266") is True


def test_is_action_mode_detects_action_payload_with_space():
    assert is_action_mode_request("what is the action payload for this error?") is True


def test_is_action_mode_detects_payload_alone():
    assert is_action_mode_request("I need the payload for FWF266") is True


def test_is_action_mode_detects_get_action():
    assert is_action_mode_request("get action for this FWF266 error") is True


def test_is_action_mode_false_for_plain_error_log():
    log = (
        "-F-,FWF266,PH382E$4115222E,Line conductor model was not found in global data.,"
        "Record name: Line Field name: CondModA,Station External Device: PH382E$4115222E,"
        "OH_653_A_2PH_653_A_N_2.9KV,,,,ALOLA,,PH382E$4115222E,ENG"
    )
    # A bare error log has no action keywords – triage mode should be used.
    assert is_action_mode_request(log) is False


def test_is_action_mode_false_for_question():
    assert is_action_mode_request("why did FWF266 occur?") is False


def test_is_action_mode_case_insensitive():
    assert is_action_mode_request("show me the ACTION_PAYLOAD") is True


# ---------------------------------------------------------------------------
# _parse_conductor_group
# ---------------------------------------------------------------------------


def test_parse_conductor_group_float_voltage():
    base, v = _parse_conductor_group("OH_653_A_2PH_653_A_N_2.9KV")
    assert base == "OH_653_A_2PH_653_A_N_"
    assert v == pytest.approx(2.9)


def test_parse_conductor_group_integer_voltage():
    base, v = _parse_conductor_group("OH_653_A_2PH_653_A_N_4KV")
    assert base == "OH_653_A_2PH_653_A_N_"
    assert v == pytest.approx(4.0)


def test_parse_conductor_group_unknown_returns_none():
    base, v = _parse_conductor_group("OH_653_A_2PH_653_A_N_UNKNOWN")
    assert base is None
    assert v is None


# ---------------------------------------------------------------------------
# _format_voltage
# ---------------------------------------------------------------------------


def test_format_voltage_integer():
    assert _format_voltage(4.0) == "4"
    assert _format_voltage(12.0) == "12"


def test_format_voltage_float():
    assert _format_voltage(2.4) == "2.4"
    assert _format_voltage(2.9) == "2.9"


# ---------------------------------------------------------------------------
# resolve – using a minimal synthetic global.csv
# ---------------------------------------------------------------------------

_GLOBAL_CSV_HEADER = (
    "Composite_Switch_Model,0,INDEX,NAME_COMPSWMOD\n"
    "Composite_Switch_Model,1,COMP_SW_1,PESING-2\n"
    "Conductor_Model,0,INDEX,NAME_CONDMOD,DISTCOND_CONDMOD,RPHASE_CONDMOD\n"
)

# Four synthetic Conductor_Model rows for prefix OH_TEST_N_
_COND_ROWS = [
    "Conductor_Model,1,COND_A,OH_TEST_N_4KV,TRUE,0.1\n",    # diff = 1.1 from 2.9
    "Conductor_Model,1,COND_B,OH_TEST_N_12KV,TRUE,0.1\n",   # diff = 9.1
    "Conductor_Model,1,COND_C,OH_TEST_N_2.4KV,TRUE,0.1\n",  # diff = 0.5 (closest)
    "Conductor_Model,1,COND_D,OH_TEST_N_UNKNOWN,TRUE,0.1\n",  # no voltage → skip
]


@pytest.fixture()
def synthetic_global_csv(tmp_path):
    """Write a small global.csv file and return its path."""
    csv_path = tmp_path / "global.csv"
    content = _GLOBAL_CSV_HEADER + "".join(_COND_ROWS)
    csv_path.write_text(content, encoding="utf-8")
    return str(csv_path)


def _make_error_log(conductor_group: str) -> str:
    return (
        f"-F-,FWF266,PH382E$4115222E,Line conductor model was not found in global data.,"
        f"Record name: Line Field name: CondModA,Station External Device: PH382E$4115222E,"
        f"{conductor_group},,,,ALOLA,,PH382E$4115222E,ENG"
    )


def test_resolve_returns_closest_match(synthetic_global_csv):
    log = _make_error_log("OH_TEST_N_2.9KV")
    result = resolve(log, synthetic_global_csv)
    assert result is not None
    assert isinstance(result, FWF266Resolution)
    # Closest to 2.9 is COND_C at 2.4KV
    assert "COND_Ca" in result.global_csv_line_text
    assert "OH_TEST_N_2.9KV" in result.global_csv_line_text


def test_resolve_line_number_is_reference_plus_one(synthetic_global_csv):
    log = _make_error_log("OH_TEST_N_2.9KV")
    result = resolve(log, synthetic_global_csv)
    assert result is not None
    # COND_C is at line index:
    # 0: Composite_Switch_Model header
    # 1: Composite_Switch_Model data
    # 2: Conductor_Model header
    # 3: COND_A
    # 4: COND_B
    # 5: COND_C  ← reference
    # 6: COND_D
    assert result.global_csv_line_number == 6  # 5 + 1


def test_resolve_tie_broken_by_higher_voltage(tmp_path):
    """When two candidates are equidistant, the higher voltage wins."""
    csv_path = tmp_path / "global.csv"
    content = (
        "Conductor_Model,0,INDEX,NAME_CONDMOD,DISTCOND_CONDMOD,RPHASE_CONDMOD\n"
        "Conductor_Model,1,COND_LO,OH_TIE_N_2KV,TRUE,0.1\n"   # diff = 2 from 4
        "Conductor_Model,1,COND_HI,OH_TIE_N_6KV,TRUE,0.1\n"   # diff = 2 from 4 → winner
    )
    csv_path.write_text(content, encoding="utf-8")
    log = _make_error_log("OH_TIE_N_4KV")
    result = resolve(log, str(csv_path))
    assert result is not None
    assert "COND_HIa" in result.global_csv_line_text


def test_resolve_returns_none_for_missing_file():
    log = _make_error_log("OH_TEST_N_2.9KV")
    result = resolve(log, "/nonexistent/path/global.csv")
    assert result is None


def test_resolve_returns_none_for_no_prefix_match(synthetic_global_csv):
    log = _make_error_log("OH_NOMATCH_N_2.9KV")
    result = resolve(log, synthetic_global_csv)
    assert result is None


def test_resolve_returns_none_for_unparseable_voltage(synthetic_global_csv):
    # Column 7 has no voltage suffix
    log = _make_error_log("OH_TEST_N_UNKNOWN")
    result = resolve(log, synthetic_global_csv)
    assert result is None


def test_resolve_returns_none_for_short_log(synthetic_global_csv):
    result = resolve("-F-,FWF266,only,three,fields", synthetic_global_csv)
    assert result is None


def test_resolve_confidence_in_range(synthetic_global_csv):
    log = _make_error_log("OH_TEST_N_2.9KV")
    result = resolve(log, synthetic_global_csv)
    assert result is not None
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Integration: resolve against the real global.csv (if present)
# ---------------------------------------------------------------------------

_REAL_GLOBAL_CSV = os.path.join(
    os.path.dirname(__file__),
    "..",
    "docs",
    "configuration_files",
    "global.csv",
)

_EXAMPLE_LOG = (
    "-F-,FWF266,PH382E$4115222E,Line conductor model was not found in global data.,"
    "Record name: Line Field name: CondModA,Station External Device: PH382E$4115222E,"
    "OH_653_A_2PH_653_A_N_2.9KV,,,,ALOLA,,PH382E$4115222E,ENG"
)


@pytest.mark.skipif(
    not os.path.exists(_REAL_GLOBAL_CSV),
    reason="real global.csv not present",
)
def test_resolve_real_global_csv_fwf266_example():
    """Validate the resolver against the actual global.csv with the example error log."""
    result = resolve(_EXAMPLE_LOG, _REAL_GLOBAL_CSV)
    assert result is not None, "Resolver returned None for the real global.csv"

    # The closest match to 2.9KV in the OH_653_A_2PH_653_A_N_ group is 2.4KV (COND_578a).
    assert "COND_578aa" in result.global_csv_line_text, (
        f"Expected COND_578aa in line_text, got: {result.global_csv_line_text[:80]}"
    )
    assert "OH_653_A_2PH_653_A_N_2.9KV" in result.global_csv_line_text, (
        f"Expected updated Conductor_Group in line_text, got: {result.global_csv_line_text[:80]}"
    )
    # COND_578a is at 0-based line 766 in the real file; insert at 767.
    assert result.global_csv_line_number == 767, (
        f"Expected line_number=767, got: {result.global_csv_line_number}"
    )
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# format_fwf266_action_payload_block – combined response tests
# ---------------------------------------------------------------------------


def test_action_payload_block_contains_json_code_fence():
    """The action payload block must contain a JSON code fence."""
    block = format_fwf266_action_payload_block(
        global_csv_line_text="Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE",
        global_csv_line_number=42,
        confidence=0.9,
        notes="test note",
    )
    assert "```json" in block
    assert "```" in block


def test_action_payload_block_contains_required_fields():
    """The action payload block must include all required action_payload fields."""
    line_text = "Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE"
    line_number = 42
    block = format_fwf266_action_payload_block(
        global_csv_line_text=line_text,
        global_csv_line_number=line_number,
        confidence=0.9,
        notes="test note",
    )
    # Extract JSON from code block
    json_start = block.index("```json") + len("```json")
    json_end = block.index("```", json_start)
    payload = json.loads(block[json_start:json_end].strip())

    assert len(payload["actions"]) == 1
    action = payload["actions"][0]
    assert action["action"] == "propose_global_csv_insert"
    assert action["global_csv_line_text"] == line_text
    assert action["global_csv_line_number"] == line_number
    assert payload["confidence"] == 0.9
    assert payload["notes"] == "test note"


def test_action_payload_block_has_section_header():
    """The block must have an 'Action Payload' heading so it stands out in chat."""
    block = format_fwf266_action_payload_block(
        global_csv_line_text="Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE",
        global_csv_line_number=1,
        confidence=0.8,
        notes="note",
    )
    assert "Action Payload" in block


def test_combined_response_contains_both_explanation_and_payload(synthetic_global_csv):
    """Simulate the _handle_query pattern: LLM text + appended payload block always present."""
    log = _make_error_log("OH_TEST_N_2.9KV")
    result = resolve(log, synthetic_global_csv)
    assert result is not None

    # Simulate what _handle_query does: LLM answer + appended block
    llm_text = "The missing Line Conductor Model OH_TEST_N_2.9KV was resolved using the closest voltage reference."
    payload_block = format_fwf266_action_payload_block(
        global_csv_line_text=result.global_csv_line_text,
        global_csv_line_number=result.global_csv_line_number,
        confidence=result.confidence,
        notes=result.notes,
    )
    full_response = llm_text + payload_block

    # Both the natural-language explanation and the action_payload must be present.
    assert "Line Conductor Model" in full_response        # text explanation
    assert "propose_global_csv_insert" in full_response  # action payload
    assert "```json" in full_response                    # valid JSON code block


# ---------------------------------------------------------------------------
# format_fwf266_action_only_response – Action Mode output
# ---------------------------------------------------------------------------


def test_action_only_response_is_bare_json_code_block():
    """Action Mode response must be only a JSON code block with no extra text."""
    response = format_fwf266_action_only_response(
        global_csv_line_text="Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE",
        global_csv_line_number=42,
        confidence=0.9,
        notes="test note",
    )
    assert response.startswith("```json")
    assert response.strip().endswith("```")


def test_action_only_response_contains_valid_json():
    """The action-only block must contain fully valid JSON."""
    line_text = "Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE"
    response = format_fwf266_action_only_response(
        global_csv_line_text=line_text,
        global_csv_line_number=99,
        confidence=0.85,
        notes="note",
    )
    json_str = response.replace("```json", "").replace("```", "").strip()
    payload = json.loads(json_str)
    assert payload["actions"][0]["global_csv_line_text"] == line_text
    assert payload["actions"][0]["global_csv_line_number"] == 99
    assert payload["confidence"] == 0.85


def test_action_only_response_has_no_introductory_text():
    """Action Mode must not include human-readable text outside the code fence."""
    response = format_fwf266_action_only_response(
        global_csv_line_text="Conductor_Model,1,COND_Xa,OH_TEST_N_2.9KV,TRUE",
        global_csv_line_number=1,
        confidence=0.9,
        notes="note",
    )
    # Strip the code block – nothing should remain
    stripped = response.replace("```json", "").replace("```", "").strip()
    # The only content should be parseable JSON (no extra prose)
    json.loads(stripped)  # raises if invalid
