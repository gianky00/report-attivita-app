"""
Test unitari per la gestione delle richieste nel database.
Copre src/modules/database/db_requests.py.
"""

import pandas as pd
import pytest
from modules.database.db_requests import (
    add_material_request,
    add_leave_request,
    get_material_requests,
    get_leave_requests,
    salva_storico_materiali,
    salva_storico_assenze,
    get_storico_richieste_materiali,
    get_storico_richieste_assenze
)

@pytest.fixture
def mock_db_conn(mocker):
    mock_conn = mocker.MagicMock()
    mocker.patch("modules.database.db_requests.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_add_material_request(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_material_request({"ID": "R1"}) is True

def test_add_leave_request(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_leave_request({"ID": "L1"}) is True

def test_get_material_requests(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_material_requests()
    assert not df.empty
    assert mock_db_conn.close.called

def test_get_leave_requests(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_leave_requests()
    assert not df.empty
    assert mock_db_conn.close.called

def test_salva_storico_materiali(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert salva_storico_materiali({"id": "S1"}) is True

def test_salva_storico_assenze(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert salva_storico_assenze({"id": "S1"}) is True

def test_get_storico_richieste_materiali(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_storico_richieste_materiali()
    assert not df.empty

def test_get_storico_richieste_assenze(mocker, mock_db_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_storico_richieste_assenze()
    assert not df.empty
