"""
Test unitari per il modulo notifiche utilizzando il mocking totale della connessione.
"""

import pytest
from src.modules.notifications import (
    crea_notifica,
    leggi_notifiche,
    segna_notifica_letta,
)


@pytest.fixture
def mock_db_notifications(mocker):
    """Fixture che simula una connessione al database senza i limiti di sqlite3.Connection."""
    mock_conn = mocker.MagicMock()
    # Simula il context manager 'with conn:'
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("src.modules.notifications.get_db_connection", return_value=mock_conn)
    mocker.patch("src.modules.db_manager.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_crea_notifica_mock(mocker, mock_db_notifications):
    """Verifica la logica di creazione notifica."""
    mocker.patch("src.modules.notifications.add_notification", return_value=True)
    assert crea_notifica("123", "Messaggio Test") is True

def test_segna_notifica_letta_mock(mock_db_notifications):
    """Verifica l'aggiornamento dello stato della notifica tramite execute."""
    # Configura il mock cursor per restituire rowcount=1
    mock_cursor = mock_db_notifications.execute.return_value
    mock_cursor.rowcount = 1

    assert segna_notifica_letta("N1") is True
    assert mock_db_notifications.execute.called

def test_leggi_notifiche_mock(mocker, mock_db_notifications):
    """Verifica il recupero delle notifiche."""
    mocker.patch("src.modules.notifications.get_notifications_for_user", return_value=[{"Messaggio": "M1"}])
    res = leggi_notifiche("123")
    assert len(res) == 1
    assert res[0]["Messaggio"] == "M1"
