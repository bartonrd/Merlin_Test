"""
tests/test_log_parser.py – Unit tests for error log detection and parsing.
"""
import pytest

from app.reasoning.log_parser import parse_log, LogSignature


# ---------------------------------------------------------------------------
# is_log detection
# ---------------------------------------------------------------------------

PYTHON_TRACEBACK = """\
Traceback (most recent call last):
  File "app.py", line 42, in <module>
    result = process(data)
  File "processor.py", line 17, in process
    raise ValueError("invalid input")
ValueError: invalid input
"""

JAVA_OOM = """\
FATAL  heap allocation failed: out of memory
java.lang.OutOfMemoryError: Java heap space
  at com.company.pipeline.transform.DataTransformer.process(DataTransformer.java:142)
  at com.company.pipeline.worker.Worker.run(Worker.java:88)
"""

K8S_LOG = """\
2024-05-08T09:14:55Z [ERROR] container data-worker exceeded memory limit
2024-05-08T09:14:56Z [FATAL] OOMKilled: container terminated by kernel
"""

HTTP_ERROR_LOG = """\
2024-03-12T14:23:01Z [ERROR] payments-api: upstream responded with HTTP 500
2024-03-12T14:23:02Z [ERROR] FATAL: remaining connection slots are reserved
"""

NORMAL_QUESTION = "What is the deployment process for the payments service?"
SHORT_ERROR = "error connecting to database"  # single line, should NOT trigger


class TestIsLog:
    def test_python_traceback_detected(self):
        assert parse_log(PYTHON_TRACEBACK).is_log is True

    def test_java_oom_detected(self):
        assert parse_log(JAVA_OOM).is_log is True

    def test_k8s_log_detected(self):
        assert parse_log(K8S_LOG).is_log is True

    def test_http_error_log_detected(self):
        assert parse_log(HTTP_ERROR_LOG).is_log is True

    def test_normal_question_not_detected(self):
        assert parse_log(NORMAL_QUESTION).is_log is False

    def test_empty_string(self):
        assert parse_log("").is_log is False


# ---------------------------------------------------------------------------
# Error code extraction
# ---------------------------------------------------------------------------

class TestErrorCodeExtraction:
    def test_http_status_extracted(self):
        sig = parse_log("Response status 503 from upstream service")
        assert any("503" in code for code in sig.error_codes)

    def test_ora_code_extracted(self):
        sig = parse_log("ORA-00942: table or view does not exist\nORA-00942 repeated")
        assert any("ORA-00942" in code for code in sig.error_codes)

    def test_exit_code_extracted(self):
        sig = parse_log("Process exited with exit code 137\n[ERROR] OOMKilled")
        assert any("137" in code for code in sig.error_codes)

    def test_no_false_positive_in_normal_text(self):
        sig = parse_log("The team has 5 members and released version 2.0 today.")
        # No real error codes should fire
        assert len(sig.error_codes) == 0


# ---------------------------------------------------------------------------
# Exception type extraction
# ---------------------------------------------------------------------------

class TestExceptionExtraction:
    def test_python_valueerror_extracted(self):
        sig = parse_log(PYTHON_TRACEBACK)
        assert "ValueError" in sig.exception_types

    def test_java_oom_exception_extracted(self):
        sig = parse_log(JAVA_OOM)
        assert "OutOfMemoryError" in sig.exception_types

    def test_nullpointerexception(self):
        sig = parse_log("NullPointerException at line 42\n[ERROR] crash")
        assert "NullPointerException" in sig.exception_types

    def test_no_exception_in_normal_text(self):
        sig = parse_log(NORMAL_QUESTION)
        assert sig.exception_types == []


# ---------------------------------------------------------------------------
# search_query generation
# ---------------------------------------------------------------------------

class TestSearchQuery:
    def test_search_query_nonempty_for_log(self):
        sig = parse_log(PYTHON_TRACEBACK)
        assert sig.search_query.strip()

    def test_search_query_uses_exception_for_log(self):
        sig = parse_log(PYTHON_TRACEBACK)
        assert "ValueError" in sig.search_query

    def test_search_query_fallback_for_normal_text(self):
        sig = parse_log(NORMAL_QUESTION)
        # Falls back to first 200 chars of the query
        assert sig.search_query == NORMAL_QUESTION[:200]

    def test_search_query_nonempty_for_oom(self):
        sig = parse_log(JAVA_OOM)
        assert "OutOfMemoryError" in sig.search_query
