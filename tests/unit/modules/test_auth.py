"""
Test unitari per il modulo di autenticazione e gestione utenti.
"""

from src.modules.auth import (
    authenticate_user,
    get_user_by_matricola,
    log_access_attempt,
    reset_user_password,
)


def test_get_user_by_matricola_success(mocker):
    mock_conn = mocker.patch("src.modules.auth.get_db_connection")
    mock_cursor = mock_conn.return_value.cursor.return_value
    mock_cursor.fetchone.return_value = {"Matricola": "123", "Nome Cognome": "Test"}
    assert get_user_by_matricola("123") is not None


def test_log_access_attempt_success(mocker):
    mocker.patch("src.modules.auth.get_db_connection")
    assert log_access_attempt("user", "success") is True


def test_reset_user_password(mocker):
    mocker.patch("src.modules.auth.update_user", return_value=True)
    assert reset_user_password("123") is True


def test_authenticate_user_fail(mocker):
    mocker.patch("src.modules.auth.get_db_connection")
    mock_cursor = mocker.patch(
        "src.modules.auth.get_db_connection"
    ).return_value.cursor.return_value
    mock_cursor.fetchone.return_value = [1]  # COUNT = 1
    mocker.patch("src.modules.auth.get_user_by_matricola", return_value=None)
    status, _ = authenticate_user("999", "pass")
    assert status == "FAILED"
