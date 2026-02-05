"""
Test per il meccanismo di retry in caso di database lock.
"""

import sqlite3
import pytest
import time
from unittest.mock import MagicMock, patch
from core.database import retry_on_lock

def test_retry_on_lock_success_after_failure():
    """Verifica che il retry funzioni se il lock viene rilasciato al secondo tentativo."""
    mock_func = MagicMock()
    # Primo tentativo fallisce per lock, secondo riesce
    mock_func.side_effect = [sqlite3.OperationalError("database is locked"), "success"]
    
    decorated = retry_on_lock(retries=3, delay=0.1)(mock_func)
    result = decorated()
    
    assert result == "success"
    assert mock_func.call_count == 2

def test_retry_on_lock_max_retries_exceeded():
    """Verifica che venga sollevata l'eccezione dopo aver esaurito i tentativi."""
    mock_func = MagicMock()
    mock_func.side_effect = sqlite3.OperationalError("database is locked")
    
    decorated = retry_on_lock(retries=2, delay=0.1)(mock_func)
    
    with pytest.raises(sqlite3.OperationalError) as excinfo:
        decorated()
    
    assert "locked" in str(excinfo.value).lower()
    assert mock_func.call_count == 2

def test_retry_on_lock_other_error_no_retry():
    """Verifica che errori diversi dal lock non attivino il retry."""
    mock_func = MagicMock()
    mock_func.side_effect = sqlite3.OperationalError("table not found")
    
    decorated = retry_on_lock(retries=3, delay=0.1)(mock_func)
    
    with pytest.raises(sqlite3.OperationalError) as excinfo:
        decorated()
    
    assert "table not found" in str(excinfo.value).lower()
    assert mock_func.call_count == 1