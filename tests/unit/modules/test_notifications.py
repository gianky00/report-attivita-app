"""
Test unitari per il modulo notifiche.
"""

import pytest
from unittest.mock import MagicMock
from modules.notifications import crea_notifica, segna_notifica_letta, leggi_notifiche

@pytest.fixture
def mock_db_notifications(mocker):
    """Fixture che simula una connessione al database core."""
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    # Patch DatabaseEngine.get_connection usato direttamente in notifications.py
    mocker.patch("core.database.DatabaseEngine.get_connection", return_value=mock_conn)
    return mock_conn

def test_crea_notifica_mock(mocker):
    # Patch add_notification dove viene CONSUMATA (in notifications.py)
    mocker.patch("modules.notifications.add_notification", return_value=True)
    assert crea_notifica("12345", "Messaggio test") is True

def test_segna_notifica_letta_mock(mocker, mock_db_notifications):
    # Configura il cursore per restituire rowcount > 0
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_db_notifications.execute.return_value = mock_cursor
    
    assert segna_notifica_letta("ID_NOTIF") is True
    assert mock_db_notifications.execute.called

def test_leggi_notifiche_mock(mocker):
    # Patch get_notifications_for_user dove viene CONSUMATA (in notifications.py)
    mocker.patch("modules.notifications.get_notifications_for_user", return_value=[
        {"ID_Notifica": "N1", "Timestamp": "2025", "Messaggio": "M1", "Stato": "letta"}
    ])
    df = leggi_notifiche("12345")
    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]["ID_Notifica"] == "N1"
