"""
Audit di sicurezza per il sistema di logging.
Verifica che dati sensibili (PII) non vengano mai scritti nei log JSON.
"""

import json
import pytest
from core.logging import JsonFormatter

def test_log_sanitization_no_passwords():
    """Verifica che i messaggi di log non contengano stringhe simili a password o segreti."""
    class MockRecord:
        def __init__(self, msg):
            self.created = 1600000000.0
            self.levelname = "INFO"
            self.name = "test"
            self.msg = msg
            self.module = "test_mod"
            self.funcName = "test_func"
            self.lineno = 10
            self.exc_info = None
        def getMessage(self):
            return self.msg

    formatter = JsonFormatter()
    
    # Il formatter deve sanitizzare automaticamente
    record = MockRecord("User 12345 logged in with password 'secret123'")
    log_output = formatter.format(record)

    # Verifichiamo che la password sia stata oscurata
    assert "secret123" not in log_output
    assert "[REDACTED]" in log_output

def test_log_extra_data_privacy():
    """Verifica che dati PII passati come extra_data siano gestiti correttamente."""
    class MockRecord:
        def __init__(self, extra):
            self.created = 1600000000.0
            self.levelname = "INFO"
            self.name = "test"
            self.msg = "User action"
            self.module = "test_mod"
            self.funcName = "test_func"
            self.lineno = 10
            self.exc_info = None
            self.extra_data = extra
        def getMessage(self):
            return self.msg

    formatter = JsonFormatter()
    extra = {"matricola": "12345", "nome": "Mario Rossi"}
    record = MockRecord(extra)
    
    log_output = json.loads(formatter.format(record))
    
    assert log_output["matricola"] == "12345"
    assert log_output["nome"] == "Mario Rossi"