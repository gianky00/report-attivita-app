"""
Test unitari per le funzioni di sistema del database.
Copre src/modules/database/db_system.py.
"""

import sqlite3
import pandas as pd
import pytest
from modules.database.db_system import (
    add_assignment_exclusion,
    get_globally_excluded_activities,
    get_notifications_for_user,
    add_notification,
    count_unread_notifications,
    save_table_data,
    get_table_data,
    get_table_names
)

@pytest.fixture
def mock_db(mocker):
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("modules.database.db_system.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_add_assignment_exclusion(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_assignment_exclusion("M123", "ACT1") is True

def test_get_globally_excluded_activities(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_all", return_value=[{"id_attivita": "A1"}])
    res = get_globally_excluded_activities()
    assert res == ["A1"]

def test_get_notifications_for_user(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_all", return_value=[{"ID": 1}])
    res = get_notifications_for_user("M123")
    assert len(res) == 1

def test_add_notification(mocker):
    mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_notification({"ID": "N1", "Msg": "Test"}) is True

def test_count_unread_notifications(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value={"count": 5})
    assert count_unread_notifications("M123") == 5

def test_count_unread_notifications_none(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_one", return_value=None)
    assert count_unread_notifications("M123") == 0

def test_save_table_data_success(mock_db):
    df = pd.DataFrame([{"col": 1}])
    assert save_table_data(df, "test_table") is True

def test_save_table_data_error(mocker, mock_db):
    df = pd.DataFrame([{"col": 1}])
    # Mockiamo to_sql per lanciare un errore
    mocker.patch.object(pd.DataFrame, "to_sql", side_effect=sqlite3.Error("SQL Error"))
    assert save_table_data(df, "test_table") is False

def test_get_table_data(mocker, mock_db):
    mocker.patch("pandas.read_sql_query", return_value=pd.DataFrame([{"id": 1}]))
    df = get_table_data("test_table")
    assert not df.empty

def test_get_table_names(mocker):
    mocker.patch("core.database.DatabaseEngine.fetch_all", return_value=[
        {"name": "t1"}, {"name": "sqlite_stat"}, {"name": "t2"}
    ])
    res = get_table_names()
    assert res == ["t1", "t2"]