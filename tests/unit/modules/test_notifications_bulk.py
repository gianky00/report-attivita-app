"""
Test di efficienza per operazioni massive sulle notifiche.
"""

import pytest
from src.modules.notifications import segna_tutte_lette

def test_segna_tutte_lette_single_query(mocker):
    """Verifica che tutte le notifiche vengano segnate come lette con una sola operazione SQL."""
    mock_db = mocker.patch("src.modules.notifications.get_db_connection")
    mock_conn = mock_db.return_value
    mock_conn.__enter__.return_value = mock_conn
    
    matricola = "12345"
    success = segna_tutte_lette(matricola)
    
    assert success is True
    # Verifichiamo che execute sia stato chiamato esattamente una volta (transazione a parte)
    assert mock_conn.execute.call_count == 1
    
    query = mock_conn.execute.call_args[0][0]
    params = mock_conn.execute.call_args[0][1]
    
    assert "UPDATE notifiche" in query
    assert "WHERE Destinatario_Matricola = ?" in query
    assert params == (matricola,)
