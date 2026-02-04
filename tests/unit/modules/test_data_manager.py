"""
Test unitari per il modulo Data Manager.
"""

import datetime

from src.modules.data_manager import _match_partial_name, scrivi_o_aggiorna_risposta


def test_match_partial_name_logic():
    assert _match_partial_name("Luca Garro", "Luca Garro") is True
    assert _match_partial_name("Garro L.", "Luca Garro") is True
    assert _match_partial_name("M. Rossi", "Mario Rossi") is True


def test_scrivi_o_aggiorna_risposta_mock(mocker):
    """Verifica il salvataggio di un report nel database."""
    mock_db = mocker.patch("src.modules.data_manager.get_db_connection")
    mock_cursor = mock_db.return_value.cursor.return_value
    mock_cursor.fetchone.return_value = ["Tecnico Test"]  # Nome Cognome

    mocker.patch("src.modules.data_manager.st.cache_data.clear")
    mocker.patch("src.modules.email_sender.invia_email_con_outlook_async")

    dati = {"descrizione": "PdL 123456 - Test", "stato": "Completato", "report": "Ok"}
    data_rif = datetime.date(2025, 1, 1)

    success = scrivi_o_aggiorna_risposta(dati, "12345", data_rif)

    assert success is True
    assert mock_db.return_value.__enter__.called  # Transazione aperta
