"""
Test unitari per il modulo Data Manager e sottomoduli correlati.
"""

import datetime

from modules.importers.excel_giornaliera import _match_partial_name
from modules.reports_manager import scrivi_o_aggiorna_risposta


def test_match_partial_name_logic():
    assert _match_partial_name("Luca Garro", "Luca Garro") is True
    assert _match_partial_name("Garro L.", "Luca Garro") is True
    assert _match_partial_name("M. Rossi", "Mario Rossi") is True


def test_scrivi_o_aggiorna_risposta_mock(mocker):
    """Verifica il salvataggio di un report nel database."""
    # Aggiorniamo i mock per puntare al DatabaseEngine usato in reports_manager
    mock_engine = mocker.patch("modules.reports_manager.DatabaseEngine.get_connection")
    mock_conn = mock_engine.return_value
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = ["Tecnico Test"]  # Nome Cognome

    # Patch st.cache_data
    mocker.patch("streamlit.cache_data")
    mocker.patch("modules.reports_manager._send_validation_email")

    dati = {"descrizione": "PdL 123456 - Test", "stato": "Completato", "report": "Ok"}
    data_rif = datetime.date(2025, 1, 1)

    success = scrivi_o_aggiorna_risposta(dati, "12345", data_rif)

    assert success is True
    # In reports_manager.py, scrivi_o_aggiorna_risposta usa DatabaseEngine.get_connection()
    # e poi usa la connessione nel context manager 'with conn:'
    assert mock_conn.__enter__.called
