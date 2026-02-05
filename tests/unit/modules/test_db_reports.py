"""
Test per la gestione dei report nel database.
"""

from modules.database.db_reports import move_report_atomically

def test_move_report_atomically_success(mocker):
    """Verifica lo spostamento atomico di un report tra tabelle."""
    # Mock di get_report_by_id
    report_data = {"id_report": "R1", "testo": "Test"}
    mocker.patch("src.modules.database.db_reports.get_report_by_id", return_value=report_data)
    
    # Mock della connessione
    mock_conn_obj = mocker.MagicMock()
    mock_conn_obj.__enter__.return_value = mock_conn_obj # Context manager returns connection
    mocker.patch("src.modules.database.db_reports.get_db_connection", return_value=mock_conn_obj)
    
    success = move_report_atomically("R1", "sorgente", "dest")
    
    assert success is True
    # Verifica che siano stati chiamati INSERT e DELETE sulla connessione
    calls = mock_conn_obj.execute.call_args_list
    assert any("INSERT INTO dest" in str(c) for c in calls)
    assert any("DELETE FROM sorgente" in str(c) for c in calls)

def test_move_report_atomically_not_found(mocker):
    """Verifica che lo spostamento fallisca se il report non esiste."""
    mocker.patch("src.modules.database.db_reports.get_report_by_id", return_value=None)
    assert move_report_atomically("999", "s", "d") is False
