"""
Test unitari per la gestione dei report nel database.
Copre il modulo src/modules/database/db_reports.py.
"""

import sqlite3
import pandas as pd
import pytest
from modules.database.db_reports import (
    move_report_atomically,
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
    get_unvalidated_reports_by_technician
)

@pytest.fixture
def mock_db(mocker):
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("modules.database.db_reports.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_get_reports_to_validate(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_reports_to_validate()
    assert len(df) == 1

def test_delete_reports_by_ids_empty():
    assert delete_reports_by_ids([]) is True

def test_delete_reports_by_ids_success(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert delete_reports_by_ids(["R1", "R2"]) is True

def test_process_and_commit_validated_reports_success(mock_db):
    reports = [{"id_report": "R1", "val": "data"}]
    assert process_and_commit_validated_reports(reports) is True
    assert mock_db.execute.called

def test_process_and_commit_validated_reports_error(mock_db):
    mock_db.execute.side_effect = sqlite3.Error("DB Error")
    reports = [{"id_report": "R1"}]
    assert process_and_commit_validated_reports(reports) is False

def test_get_unvalidated_relazioni(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_unvalidated_relazioni()
    assert len(df) == 1

def test_process_and_commit_validated_relazioni_success(mock_db):
    df = pd.DataFrame([{"id_relazione": "REL1"}])
    assert process_and_commit_validated_relazioni(df, "ADMIN1") is True

def test_salva_report_intervento(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert salva_report_intervento({"pdl": "P1"}) is True

def test_salva_relazione(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert salva_relazione({"id": "R1"}) is True

def test_get_validated_reports_invalid():
    df = get_validated_reports("invalid_table")
    assert df.empty

def test_get_validated_reports_valid(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_validated_reports("relazioni")
    assert not df.empty

def test_get_validated_intervention_reports_filter(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_validated_intervention_reports("M123")
    assert len(df) == 1

def test_get_validated_intervention_reports_all(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_validated_intervention_reports()
    assert len(df) == 1

def test_get_report_by_id_invalid_table():
    assert get_report_by_id("R1", "invalid") is None

def test_get_report_by_id_success(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"id": "R1"})
    res = get_report_by_id("R1", "report_interventi")
    assert res is not None

def test_delete_report_by_id_invalid():
    assert delete_report_by_id("R1", "invalid") is False

def test_delete_report_by_id_success(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert delete_report_by_id("R1", "report_da_validare") is True

def test_insert_report_invalid():
    assert insert_report({}, "invalid") is False

def test_insert_report_success(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert insert_report({"id_report": "R1"}, "report_da_validare") is True

def test_move_report_atomically_invalid_tables():
    assert move_report_atomically("R1", "invalid", "report_interventi") is False

def test_move_report_atomically_not_found(mocker):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value=None)
    assert move_report_atomically("R1", "report_da_validare", "report_interventi") is False

def test_move_report_atomically_success(mocker, mock_db):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value={"id": "R1", "txt": "T"})
    assert move_report_atomically("R1", "report_da_validare", "report_interventi") is True

def test_move_report_atomically_error(mocker, mock_db):
    mocker.patch("modules.database.db_reports.get_report_by_id", return_value={"id": "R1"})
    mock_db.execute.side_effect = sqlite3.Error("SQL Error")
    assert move_report_atomically("R1", "report_da_validare", "report_interventi") is False

def test_get_unvalidated_reports_by_technician(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_unvalidated_reports_by_technician("M123")
    assert len(df) == 1
