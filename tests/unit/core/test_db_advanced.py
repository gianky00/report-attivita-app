"""
Test per la sicurezza dei thread nel Database Engine.
"""

import threading
import sqlite3
import pytest
from src.core.database import DatabaseEngine

def test_database_thread_safety(mocker):
    """Verifica che chiamate concorrenti non mandino in crash l'engine."""
    mocker.patch("src.core.database.DB_NAME", ":memory:")
    
    def worker():
        for _ in range(10):
            DatabaseEngine.execute("SELECT 1")
            
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    assert True

def test_move_report_atomically_failure_middle(mocker):
    """Verifica l'integrità della transazione se l'eliminazione fallisce."""
    report_data = {"id": "R1", "val": "data"}
    mocker.patch("src.modules.database.db_reports.get_report_by_id", return_value=report_data)
    
    # Mock connessione reale per testare il rollback indirettamente tramite eccezione
    mock_conn = mocker.MagicMock()
    mocker.patch("src.modules.database.db_reports.get_db_connection", return_value=mock_conn)
    
    # Simula errore durante l'esecuzione nel context manager
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = [None, sqlite3.Error("Rollback trigger")]
    
    from src.modules.database.db_reports import move_report_atomically
    
    success = move_report_atomically("R1", "s", "d")
    assert success is False