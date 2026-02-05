"""
Test unitari per la gestione utenti nel database.
Copre src/modules/database/db_users.py.
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
    mock_conn = mocker.MagicMock()
    mocker.patch("modules.database.db_users.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_get_all_users(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_all_users()
    assert not df.empty
    assert mock_db_conn.close.called

def test_get_last_login_found(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"timestamp": "2025-01-01"})
    assert get_last_login("M123") == "2025-01-01"

def test_get_last_login_not_found(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value=None)
    assert get_last_login("M123") is None

def test_get_access_logs(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_access_logs()
    assert not df.empty

def test_get_substitution_request_by_id(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"ID": "S1"})
    assert get_substitution_request_by_id("S1") is not None

def test_delete_substitution_request(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert delete_substitution_request("S1") is True

def test_add_substitution_request(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_substitution_request({"ID": "S1"}) is True

def test_get_all_substitutions(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_all_substitutions()
    assert not df.empty
