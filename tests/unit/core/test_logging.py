"""
Test unitari per il sistema di logging strutturato.
"""

import io
import json
import logging

from core.logging import JsonFormatter, get_logger, with_context


def test_json_formatter_structure():
    """Verifica che il formatter produca un JSON con i campi attesi."""
    formatter = JsonFormatter()
    log_record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path.py",
        lineno=10,
        msg="Test message",
        args=None,
        exc_info=None,
    )

    formatted_json = formatter.format(log_record)
    data = json.loads(formatted_json)

    assert data["message"] == "Test message"
    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert "timestamp" in data


def test_logging_context_propagation():
    """Verifica che il trace_id venga correttamente iniettato tramite il contesto."""
    logger = get_logger("test_context")
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    test_trace = "unique-trace-123"
    with with_context(trace_id=test_trace):
        logger.info("Message with context")

    output = log_capture.getvalue()
    data = json.loads(output.strip().splitlines()[-1])

    assert data["trace_id"] == test_trace
    assert data["message"] == "Message with context"
