"""Tests for the log parser / triage detector."""
import pytest

from app.reasoning.log_parser import is_error_log, parse_log_signature


def test_python_traceback():
    log = """Traceback (most recent call last):
  File "app.py", line 42, in handler
    result = db.query(sql)
  File "db.py", line 17, in query
    raise DatabaseError("Connection timeout")
DatabaseError: Connection timeout"""
    assert is_error_log(log) is True
    sig = parse_log_signature(log)
    assert sig.is_log is True
    assert any("DatabaseError" in e for e in sig.exception_types)


def test_java_stacktrace():
    log = """java.lang.NullPointerException: Cannot invoke method on null
    at com.example.service.OrderService.processOrder(OrderService.java:142)
    at com.example.controller.OrderController.createOrder(OrderController.java:87)
    at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)"""
    assert is_error_log(log) is True


def test_http_error_code():
    log = "2024-01-15 14:32:01 ERROR upstream returned HTTP 504 for /api/orders"
    assert is_error_log(log) is True


def test_normal_question():
    query = "How do I restart the database connection pool?"
    assert is_error_log(query) is False


def test_normal_sentence_not_log():
    query = "What are the steps to scale the order-processor service?"
    assert is_error_log(query) is False


def test_parse_error_codes():
    log = "ORA-12541: TNS:no listener\nORA-12170: TNS:Connect timeout"
    sig = parse_log_signature(log)
    assert any("ORA-12541" in c or "ORA-12170" in c for c in sig.error_codes)


def test_parse_exception_types():
    log = """java.sql.SQLException: Timeout waiting for connection
    at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)"""
    sig = parse_log_signature(log)
    assert any("SQLException" in e for e in sig.exception_types)


def test_multiple_timestamps_detected_as_log():
    log = (
        "2024-01-01 10:00:00 INFO Starting\n"
        "2024-01-01 10:00:01 ERROR Something failed\n"
        "2024-01-01 10:00:02 CRITICAL Service down\n"
    )
    assert is_error_log(log) is True


def test_parse_http_error_codes():
    log = "2024-01-15 ERROR upstream returned HTTP 503 gateway unavailable"
    sig = parse_log_signature(log)
    assert any("503" in c for c in sig.error_codes)


def test_stack_trace_lines_captured():
    log = """Traceback (most recent call last):
  File "main.py", line 10, in <module>
    run()
  File "core.py", line 55, in run
    connect()
RuntimeError: failed to connect"""
    sig = parse_log_signature(log)
    assert sig.is_log is True
    assert len(sig.stack_trace_lines) > 0
