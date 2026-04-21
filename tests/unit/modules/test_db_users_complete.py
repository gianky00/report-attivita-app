"""
Test unitari completi per il modulo database utenti.
"""

import pandas as pd
import pytest
from modules.database.db_users import (
    get_all_users,
    get_last_login,
    get_access_logs,
    get_substitution_request_by_id,
    delete_substitution_request,
    add_substitution_request,
    get_all_substitutions
)

@pytest.fixture
def mock_db_conn(mocker):
    mock_engine = mocker.patch("modules.database.db_users.DatabaseEngine.get_connection")
    mock_conn = mock_engine.return_value
    mock_conn.close = mocker.MagicMock()
    return mock_conn

def test_get_all_users(mocker, mock_db_conn):
    # Mock per pd.read_sql_query con colonne richieste dalla logica
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Test User"}
    ]))
    df = get_all_users()
    assert not df.empty
    assert "Matricola" in df.columns

def test_get_last_login_found(mocker):
    mock_fetch = mocker.patch("modules.database.db_users.DatabaseEngine.fetch_one")
    mock_fetch.return_value = {"timestamp": "2025-01-01"}
    assert get_last_login("123") == "2025-01-01"

def test_get_last_login_not_found(mocker):
    mock_fetch = mocker.patch("modules.database.db_users.DatabaseEngine.fetch_one", return_value=None)
    assert get_last_login("123") is None

def test_get_access_logs(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_access_logs()
    assert len(df) == 1

def test_get_substitution_request_by_id(mocker):
    mock_fetch = mocker.patch("modules.database.db_users.DatabaseEngine.fetch_one")
    mock_fetch.return_value = {"ID_Richiesta": "SR1"}
    res = get_substitution_request_by_id("SR1")
    assert res["ID_Richiesta"] == "SR1"

def test_delete_substitution_request(mocker):
    mock_exec = mocker.patch("modules.database.db_users.DatabaseEngine.execute", return_value=True)
    assert delete_substitution_request("SR1") is True

def test_add_substitution_request(mocker):
    mock_exec = mocker.patch("modules.database.db_users.DatabaseEngine.execute", return_value=True)
    assert add_substitution_request({"ID_Richiesta": "SR2"}) is True

def test_get_all_substitutions(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_all_substitutions()
    assert len(df) == 1
