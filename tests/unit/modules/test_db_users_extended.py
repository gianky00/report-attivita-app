"""
Test unitari per il modulo database utenti (db_users.py).
Focalizzato sul recupero login e log di sistema.
"""

import pandas as pd
import pytest
from modules.database.db_users import get_last_login, get_access_logs

def test_get_last_login_found(mocker):
    """Verifica il recupero corretto dell'ultimo timestamp di login."""
    mock_row = {"timestamp": "2026-02-04 10:00:00"}
    mocker.patch("modules.database.db_users.DatabaseEngine.fetch_one", return_value=mock_row)
    
    last_login = get_last_login("12345")
    assert last_login == "2026-02-04 10:00:00"

def test_get_last_login_not_found(mocker):
    """Verifica il comportamento quando non ci sono log per l'utente."""
    mocker.patch("modules.database.db_users.DatabaseEngine.fetch_one", return_value=None)
    
    assert get_last_login("NONEXISTENT") is None

def test_get_access_logs_dataframe(mocker):
    """Verifica che get_access_logs restituisca un DataFrame pandas."""
    # Mocking get_db_connection per pd.read_sql_query
    mock_conn = mocker.patch("modules.database.db_users.get_db_connection")
    
    # Prepariamo dati fittizi
    data = {"timestamp": ["2026-01-01"], "username": ["test_user"], "status": ["success"]}
    mock_df = pd.DataFrame(data)
    
    # Mockiamo read_sql_query per evitare l'uso reale del DB
    mocker.patch("pandas.read_sql_query", return_value=mock_df)
    
    df = get_access_logs()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "status" in df.columns
