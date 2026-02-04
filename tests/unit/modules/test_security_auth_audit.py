"""
Audit di sicurezza per l'autenticazione e il logging.
"""

import json
import pytest
from src.modules.auth import authenticate_user, log_access_attempt
from src.core.logging import JsonFormatter
import logging

def test_login_failure_logging_privacy(mocker):
    """Verifica che i tentativi falliti non logghino password o segreti."""
    # 1. Mock DB per fallimento login
    mocker.patch("src.modules.auth.get_db_connection")
    mocker.patch("src.modules.auth.get_user_by_matricola", return_value=None)
    
    # 2. Mock del logger per catturare l'output
    mock_log = mocker.patch("src.modules.auth.logger")
    
    # Tentativo con password sensibile
    password_pericolosa = "Password123!"
    authenticate_user("UTENTE_TEST", password_pericolosa)
    
    # Verifichiamo che log_access_attempt sia stato chiamato
    # log_access_attempt registra nel DB, non necessariamente nel logger file
    # ma authenticate_user potrebbe loggare errori
    
    # 3. Test diretto del Formatter su un log record malevolo
    class MockRecord:
        def __init__(self, msg, extra=None):
            self.created = 1600000000.0
            self.levelname = "WARNING"
            self.name = "auth"
            self.msg = msg
            self.module = "auth"
            self.funcName = "authenticate"
            self.lineno = 50
            self.exc_info = None
            self.extra_data = extra or {}
        def getMessage(self): return self.msg

    formatter = JsonFormatter()
    
    # Caso: Messaggio con password nel testo
    rec1 = MockRecord(f"Fallimento login per utente con pass {password_pericolosa}")
    res1 = json.loads(formatter.format(rec1))
    assert "[REDACTED]" in res1["message"]
    assert password_pericolosa not in res1["message"]

    # Caso: Segreto 2FA nei metadati extra
    rec2 = MockRecord("Setup 2FA", extra={"2fa_secret": "JBSWY3DPEHPK3PXP"})
    res2 = json.loads(formatter.format(rec2))
    assert res2["2fa_secret"] == "********"
