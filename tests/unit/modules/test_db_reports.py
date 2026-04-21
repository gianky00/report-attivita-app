"""
Test unitari per il modulo database report.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock
from modules.database.db_reports import (
    get_reports_to_validate,
    delete_reports_by_ids,
    process_and_commit_validated_reports,
    get_unvalidated_relazioni,
    process_and_commit_validated_relazioni,
    salva_report_intervento,
    salva_relazione,
    get_validated_reports,
    get_validated_intervention_reports,
    get_report_by_id,
    delete_report_by_id,
    insert_report,
    move_report_atomically,
    get_unvalidated_reports_by_technician
)

@pytest.fixture
def mock_conn(mocker):
    mock_engine = mocker.patch("modules.database.db_reports.DatabaseEngine.get_connection")
    conn = mock_engine.return_value
    conn.__enter__.return_value = conn
    conn.execute.return_value = MagicMock()
    return conn

def test_get_reports_to_validate(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_reports_to_validate()
    assert len(df) == 1

def test_delete_reports_by_ids_empty():
    assert delete_reports_by_ids([]) is True

def test_delete_reports_by_ids_success(mocker):
    mock_exec = mocker.patch("modules.database.db_reports.DatabaseEngine.execute", return_value=True)
    assert delete_reports_by_ids(["1", "2"]) is True
    assert mock_exec.called

def test_process_and_commit_validated_reports_success(mocker, mock_conn):
    # process_and_commit_validated_reports aspetta una lista di dizionari
    reports = [{"id_report": "R1", "pdl": "123", "matricola_tecnico": "T1", "data_riferimento_attivita": "2025-01-01"}]
    assert process_and_commit_validated_reports(reports) is True
    assert mock_conn.execute.called

def test_process_and_commit_validated_reports_error(mocker, mock_conn):
    import sqlite3
    mock_conn.execute.side_effect = sqlite3.Error("DB Error")
    reports = [{"id_report": "R1"}]
    assert process_and_commit_validated_reports(reports) is False

def test_get_unvalidated_relazioni(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_unvalidated_relazioni()
    assert len(df) == 1

def test_process_and_commit_validated_relazioni_success(mocker, mock_conn):
    df = pd.DataFrame([{"id_relazione": "REL1"}])
    assert process_and_commit_validated_relazioni(df, "ADMIN1") is True
    assert mock_conn.execute.called

def test_salva_report_intervento(mocker):
    mock_exec = mocker.patch("modules.database.db_reports.DatabaseEngine.execute", return_value=True)
    assert salva_report_intervento({"id": 1}) is True

def test_salva_relazione(mocker):
    mock_exec = mocker.patch("modules.database.db_reports.DatabaseEngine.execute", return_value=True)
    assert salva_relazione({"id": 1}) is True

def test_get_validated_reports_invalid():
    # Ritorna DataFrame vuoto, non None
    df = get_validated_reports("invalid_table")
    assert isinstance(df, pd.DataFrame)
    assert df.empty

def test_get_validated_reports_valid(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_validated_reports("report_interventi")
    assert df is not None
    assert len(df) == 1

def test_get_validated_intervention_reports_filter(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    # Accetta solo un argomento opzionale: matricola_tecnico
    df = get_validated_intervention_reports("T123")
    assert len(df) == 1

def test_get_validated_intervention_reports_all(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_validated_intervention_reports()
    assert len(df) == 1

def test_get_report_by_id_invalid_table():
    assert get_report_by_id("1", "invalid") is None

def test_get_report_by_id_success(mocker):
    mock_fetch = mocker.patch("modules.database.db_reports.DatabaseEngine.fetch_one")
    mock_fetch.return_value = {"id": "1"}
    assert get_report_by_id("1", "report_interventi") == {"id": "1"}

def test_delete_report_by_id_invalid():
    assert delete_report_by_id("1", "invalid") is False

def test_delete_report_by_id_success(mocker):
    mock_exec = mocker.patch("modules.database.db_reports.DatabaseEngine.execute", return_value=True)
    assert delete_report_by_id("1", "report_interventi") is True

def test_insert_report_invalid():
    assert insert_report({}, "invalid") is False

def test_insert_report_success(mocker, mock_conn):
    # insert_report usa internamente conn.execute sia per l'insert che per l'update dei PDL
    mock_conn.execute.return_value.fetchone.return_value = None # Simula non esistente per INSERT
    assert insert_report({"id_report": "R1", "pdl": "123", "data_riferimento_attivita": "2025-01-01"}, "report_da_validare") is True
    assert mock_conn.execute.called

def test_move_report_atomically_invalid_tables():
    assert move_report_atomically("1", "invalid", "report_interventi") is False

def test_move_report_atomically_not_found(mocker):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value=None)
    assert move_report_atomically("1", "report_da_validare", "report_interventi") is False

def test_move_report_atomically_success(mocker, mock_conn):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value={"id": "1"})
    assert move_report_atomically("1", "report_da_validare", "report_interventi") is True
    assert mock_conn.execute.called

def test_move_report_atomically_error(mocker, mock_conn):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value={"id": "1"})
    # In db_reports.py: con DatabaseEngine.get_connection() e context manager 'with conn:'
    # L'eccezione viene catturata dal try-except in move_report_atomically
    import sqlite3
    mock_conn.execute.side_effect = sqlite3.Error("DB Error")
    assert move_report_atomically("1", "report_da_validare", "report_interventi") is False

def test_get_unvalidated_reports_by_technician(mocker, mock_conn):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_unvalidated_reports_by_technician("12345")
    assert len(df) == 1
