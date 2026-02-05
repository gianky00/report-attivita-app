"""
Test per la robustezza del matching nomi e parsing PdL.
"""

import datetime
import pytest
import pandas as pd
import streamlit as st
from modules.importers.excel_giornaliera import _match_partial_name
from modules.reports_manager import scrivi_o_aggiorna_risposta

def test_match_partial_name_complex():
    """Test matching nomi con iniziali e cognomi composti."""
    assert _match_partial_name("Rossi M.", "Mario Rossi") is True
    assert _match_partial_name("De Rosa G.B.", "Giovan Battista De Rosa") is True
    assert _match_partial_name("  rossi m. ", "MARIO ROSSI") is True
    assert _match_partial_name("Bianchi L.", "Mario Rossi") is False

def test_pdl_regex_extraction(mocker):
    """Verifica l'estrazione del PdL da vari formati di descrizione."""
    mocker.patch("streamlit.error")
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.cache_data.clear")
    
    # Mock connessione e cursore
    mock_conn = mocker.MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = ("Mario Rossi",)
    
    # Patchiamo get_db_connection
    mocker.patch("src.modules.reports_manager.get_db_connection", return_value=mock_conn)
    
    # Patchiamo l'invio email (importato localmente come modules.email_sender)
    mocker.patch("src.modules.email_sender.invia_email_con_outlook_async")
    
    # Dati di test
    data_rif = datetime.date(2025, 1, 1)
    payload = {
        "descrizione": "Lavori su PdL 123456 - Sostituzione componenti",
        "report": "Intervento eseguito con successo",
        "stato": "TERMINATA"
    }

    # Esecuzione
    success = scrivi_o_aggiorna_risposta(payload, "123", data_rif)
    
    # Verifiche
    assert success is True
    assert mock_cursor.execute.called
    
    # Verifichiamo che il PdL estratto sia corretto nella chiamata INSERT
    # L'ultimo execute è la INSERT (il primo era la SELECT del nome)
    insert_call = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO report_da_validare" in c[0][0]][0]
    insert_values = insert_call[0][1]
    
    # Lo schema dei dati in report_data mette 'pdl' come secondo elemento (dopo id_report)
    assert "123456" in insert_values
