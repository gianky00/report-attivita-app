"""
Test approfonditi per il modulo DB Manager utilizzando il mocking completo.
"""

import pytest
from src.modules.db_manager import (
    add_assignment_exclusion,
    add_shift_log,
    delete_booking,
    get_globally_excluded_activities,
    get_last_login,
    get_report_by_id,
    insert_report,
    update_shift,
)


@pytest.fixture
def mock_db(mocker):
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("src.modules.db_manager.get_db_connection", return_value=mock_conn)
    return mock_conn


def test_add_shift_log_mock(mock_db):
    assert add_shift_log({"ID": "L1"}) is True


def test_get_last_login_mock(mocker, mock_db):
    mock_cursor = mock_db.cursor.return_value
    mock_row = {"timestamp": "2025-01-01"}
    mock_cursor.fetchone.return_value = mock_row
    assert get_last_login("admin") == "2025-01-01"


def test_delete_booking(mock_db):
    # La firma corretta è delete_booking(booking_id, shift_id)
    mock_db.execute.return_value.rowcount = 1
    assert delete_booking("B1", "T1") is True


def test_get_report_by_id(mock_db):
    # La firma corretta è get_report_by_id(report_id, table_name)
    mock_cursor = mock_db.cursor.return_value
    mock_cursor.fetchone.return_value = {"id_report": "R1"}
    res = get_report_by_id("R1", "report_interventi")
    assert res["id_report"] == "R1"


def test_insert_report(mock_db):
    # La firma corretta è insert_report(report_data, table_name)
    assert insert_report({"col": "val"}, "table_name") is True


def test_add_assignment_exclusion(mock_db):
    assert add_assignment_exclusion("admin", "pdl-task") is True


def test_get_globally_excluded_activities(mock_db):
    mock_cursor = mock_db.cursor.return_value
    mock_cursor.fetchall.return_value = [{"id_attivita": "id1"}]
    assert "id1" in get_globally_excluded_activities()


def test_update_shift_success(mock_db):
    mock_cursor = mock_db.execute.return_value
    mock_cursor.rowcount = 1
    assert update_shift("T1", {"Descrizione": "Nuova"}) is True
