"""
Test unitari per la robustezza del parsing dei dati.
"""

import datetime
from modules.importers.excel_giornaliera import _match_partial_name
from modules.reports_manager import scrivi_o_aggiorna_risposta

def test_match_partial_name_complex():
    """Verifica la logica di matching nomi complessi."""
    assert _match_partial_name("Rossi M.", "Mario Rossi") is True
    assert _match_partial_name("G. Verdi", "Giuseppe Verdi") is True
    assert _match_partial_name("Bianchi L.A.", "Luca Antonio Bianchi") is True
    assert _match_partial_name("Mario", "Mario Rossi") is True
    assert _match_partial_name("M.R.", "Mario Rossi") is True
    assert _match_partial_name("Unknown", "Mario Rossi") is False

def test_pdl_regex_extraction(mocker):
    """Verifica l'estrazione del PdL da vari formati di descrizione."""
    mocker.patch("streamlit.error")
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.cache_data")

    # Mock per DatabaseEngine.get_connection e il cursore per recuperare il nome utente
    mock_conn = mocker.MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = ("Mario Rossi",)
    mocker.patch("core.database.DatabaseEngine.get_connection", return_value=mock_conn)

    # Mock per insert_report e invio email
    mock_insert = mocker.patch("modules.database.db_reports.insert_report", return_value=True)
    mocker.patch("modules.reports_manager._send_validation_email")

    data_rif = datetime.date(2025, 1, 1)
    
    # Caso 1: Formato standard
    payload = {
        "descrizione": "Lavori su PdL 123456 - Sostituzione componenti",
        "report": "Ok",
        "stato": "TERMINATA",
    }
    scrivi_o_aggiorna_risposta(payload, "123", data_rif)
    assert mock_insert.call_args[0][0]["pdl"] == "123456"

    # Caso 2: Formato con suffisso /C o /S
    payload["descrizione"] = "Intervento PdL 654321/C manutenzione"
    scrivi_o_aggiorna_risposta(payload, "123", data_rif)
    assert mock_insert.call_args[0][0]["pdl"] == "654321/C"
