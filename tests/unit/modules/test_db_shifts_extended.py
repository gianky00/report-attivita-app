"""
Test unitari per la gestione dei turni nel database.
Copre src/modules/database/db_shifts.py.
"""

import sqlite3
import pandas as pd
import pytest
from modules.database.db_shifts import (
    get_shifts_by_type,
    create_shift,
    update_shift,
    get_shift_by_id,
    add_shift_log,
    get_bookings_for_shift,
    add_booking,
    delete_booking,
    delete_bookings_for_shift,
    get_booking_by_user_and_shift,
    check_user_oncall_conflict,
    update_booking_user,
    get_all_bookings,
    get_bacheca_item_by_id,
    update_bacheca_item,
    add_bacheca_item,
    get_all_bacheca_items
)

@pytest.fixture
def mock_db(mocker):
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("modules.database.db_shifts.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_get_shifts_by_type_success(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_shifts_by_type("Reperibilità")
    assert len(df) == 1

def test_get_shifts_by_type_error(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", side_effect=sqlite3.Error("SQL Error"))
    df = get_shifts_by_type("Reperibilità")
    assert df.empty

def test_create_shift(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert create_shift({"ID": "T1"}) is True

def test_update_shift(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert update_shift("T1", {"Desc": "New"}) is True

def test_get_shift_by_id(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"ID": "T1"})
    assert get_shift_by_id("T1")["ID"] == "T1"

def test_add_shift_log(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_shift_log({"ID_Modifica": "L1"}) is True

def test_get_bookings_for_shift(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"ID": "B1"}]))
    df = get_bookings_for_shift("T1")
    assert len(df) == 1

def test_add_booking(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_booking({"ID_Prenotazione": "B1"}) is True

def test_delete_booking(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert delete_booking("B1", "T1") is True

def test_delete_bookings_for_shift(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert delete_bookings_for_shift("T1") is True

def test_get_booking_by_user_and_shift(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"Matricola": "123"})
    assert get_booking_by_user_and_shift("123", "T1") is not None

def test_check_user_oncall_conflict_true(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"count": 1})
    assert check_user_oncall_conflict("123", "2025-01-01") is True

def test_check_user_oncall_conflict_false(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"count": 0})
    assert check_user_oncall_conflict("123", "2025-01-01") is False

def test_update_booking_user(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert update_booking_user("T1", "OLD", "NEW") is True

def test_get_all_bookings(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"ID": 1}]))
    df = get_all_bookings()
    assert len(df) == 1

def test_get_bacheca_item_by_id(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"ID": "B1"})
    assert get_bacheca_item_by_id("B1")["ID"] == "B1"

def test_update_bacheca_item(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert update_bacheca_item("B1", {"Stato": "Preso"}) is True

def test_add_bacheca_item(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_bacheca_item({"ID": "B1"}) is True

def test_get_all_bacheca_items(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"ID": 1}]))
    df = get_all_bacheca_items()
    assert len(df) == 1
