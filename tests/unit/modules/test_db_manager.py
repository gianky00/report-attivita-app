"""
Test approfonditi per il modulo DB Manager utilizzando il mocking di DatabaseEngine.
"""

import pytest
from modules.db_manager import (
    add_assignment_exclusion,
    add_shift_log,
    delete_booking,
    get_globally_excluded_activities,
    get_last_login,
    get_report_by_id,
    insert_report,
    update_shift,
)


@pytest.fixture(autouse=True)
def mock_db_engine(mocker):
    """Patch dei metodi statici/classmethod di DatabaseEngine."""
    mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    mocker.patch("src.core.database.DatabaseEngine.fetch_one", return_value=None)
    mocker.patch("src.core.database.DatabaseEngine.fetch_all", return_value=[])
    mocker.patch("src.core.database.DatabaseEngine.insert_returning_id", return_value=1)


def test_add_shift_log_mock(mocker):
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert add_shift_log({"ID": "L1"}) is True
    assert mock_exec.called


def test_get_last_login_mock(mocker):
    mocker.patch(
        "src.core.database.DatabaseEngine.fetch_one", 
        return_value={"timestamp": "2025-01-01"}
    )
    assert get_last_login("admin") == "2025-01-01"


def test_delete_booking(mocker):
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert delete_booking("B1", "T1") is True
    assert mock_exec.called


def test_get_report_by_id(mocker):
    mocker.patch(
        "src.core.database.DatabaseEngine.fetch_one", 
        return_value={"id_report": "R1"}
    )
    res = get_report_by_id("R1", "report_interventi")
    assert res["id_report"] == "R1"


def test_insert_report(mocker):
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert insert_report({"col": "val"}, "report_interventi") is True
    assert mock_exec.called


def test_add_assignment_exclusion(mocker):
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert add_assignment_exclusion("admin", "pdl-task") is True
    assert mock_exec.called


def test_get_globally_excluded_activities(mocker):
    mocker.patch(
        "src.core.database.DatabaseEngine.fetch_all", 
        return_value=[{"id_attivita": "id1"}]
    )
    assert "id1" in get_globally_excluded_activities()


def test_update_shift_success(mocker):
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert update_shift("T1", {"Descrizione": "Nuova"}) is True
    assert mock_exec.called
