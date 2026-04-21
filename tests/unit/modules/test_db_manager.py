"""
Test unitari per il modulo db_manager (Facade) e sottomoduli.
"""

import datetime
from unittest.mock import MagicMock
from modules.db_manager import (
    add_shift_log,
    get_last_login,
    delete_booking,
    get_report_by_id,
    insert_report,
    add_assignment_exclusion,
    get_globally_excluded_activities,
    update_shift
)

def test_add_shift_log_mock(mocker):
    mock_exec = mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    # add_shift_log accetta un dizionario log_data
    log_data = {"Utente": "user", "Azione": "action", "Dettagli": "details"}
    assert add_shift_log(log_data) is True
    assert mock_exec.called

def test_get_last_login_mock(mocker):
    mock_fetch = mocker.patch("core.database.DatabaseEngine.fetch_one")
    mock_fetch.return_value = {"timestamp": "2025-01-01T10:00:00"}
    assert get_last_login("12345") == "2025-01-01T10:00:00"

def test_delete_booking(mocker):
    mock_exec = mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    # delete_booking richiede booking_id e shift_id
    assert delete_booking("B1", "S1") is True

def test_get_report_by_id(mocker):
    mock_fetch = mocker.patch("core.database.DatabaseEngine.fetch_one")
    mock_fetch.return_value = {"id_report": "R1", "testo_report": "OK"}
    res = get_report_by_id("R1", "report_interventi")
    assert res is not None
    assert res["id_report"] == "R1"

def test_insert_report(mocker):
    # insert_report in db_reports usa DatabaseEngine.get_connection() e poi conn.execute
    mock_engine = mocker.patch("core.database.DatabaseEngine.get_connection")
    mock_conn = mock_engine.return_value
    mock_conn.__enter__.return_value = mock_conn
    
    # Simula successo esecuzione query
    mock_conn.execute.return_value = MagicMock()
    
    assert insert_report({"testo_report": "val"}, "report_interventi") is True
    assert mock_conn.execute.called

def test_add_assignment_exclusion(mocker):
    mock_exec = mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_assignment_exclusion("12345", "ACT1") is True

def test_get_globally_excluded_activities(mocker):
    mock_fetch = mocker.patch("core.database.DatabaseEngine.fetch_all")
    mock_fetch.return_value = [{"id_attivita": "A1"}, {"id_attivita": "A2"}]
    res = get_globally_excluded_activities()
    assert len(res) == 2
    assert "A1" in res

def test_update_shift_success(mocker):
    mock_exec = mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert update_shift("S1", {"Stato": "Confermato"}) is True
