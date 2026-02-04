"""
Test unitari per comunicazioni, PDF e notifiche.
"""

import os
import pytest
from pathlib import Path
from src.modules.email_sender import _send_email_subprocess
from src.modules.pdf_utils import generate_on_call_pdf
from src.modules.notifications import crea_notifica, segna_tutte_lette

def test_send_email_subprocess_error_handling(mocker):
    """Verifica la gestione degli errori se il subprocess fallisce."""
    # Mock di subprocess.run per simulare un errore (returncode != 0)
    mock_run = mocker.patch("src.modules.email_sender.subprocess.run")
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Outlook Error"
    
    mock_logger = mocker.patch("src.modules.email_sender.logger")
    mocker.patch("src.modules.email_sender.Path.exists", return_value=True)
    
    _send_email_subprocess("Test", "Body")
    
    # Verifica che l'errore sia stato loggato
    mock_logger.error.assert_called()
    assert "Fallimento subprocess email" in mock_logger.error.call_args[0][0]

def test_generate_on_call_pdf_integrity(tmp_path, mocker):
    """Verifica che il PDF venga generato correttamente con i metadati attesi."""
    # Cambiamo directory di lavoro temporaneamente per evitare di scrivere nella cartella reale
    mocker.patch("src.modules.pdf_utils.Path.mkdir") # Evitiamo creazione cartella reale
    
    # Prepariamo dati minimi
    data = [
        {"Data": "2025-01-01", "RuoloOccupato": "Tecnico", "Nome Cognome": "Mario Rossi"},
        {"Data": "2025-01-01", "RuoloOccupato": "Aiutante", "Nome Cognome": "Luigi Bianchi"}
    ]
    
    # Mock dell'output per non scrivere file
    mock_pdf_output = mocker.patch("src.modules.pdf_utils.PDF.output")
    
    file_path = generate_on_call_pdf(data, "gennaio", 2025)
    
    assert file_path is not None
    assert "reperibilita_strumentale_gennaio_2025" in file_path
    assert mock_pdf_output.called

def test_notifications_bulk_operations(mocker):
    """Testa la creazione di notifiche e la logica 'Segna tutte come lette'."""
    mock_add = mocker.patch("src.modules.notifications.add_notification", return_value=True)
    mock_db = mocker.patch("src.modules.notifications.get_db_connection")
    mock_cursor = mock_db.return_value.execute.return_value
    mock_cursor.rowcount = 5 # Simula 5 righe aggiornate
    
    # 1. Creazione
    assert crea_notifica("12345", "Test messaggio") is True
    assert mock_add.called
    
    # 2. Segna tutte come lette
    assert segna_tutte_lette("12345") is True
    assert mock_db.return_value.execute.called
    args = mock_db.return_value.execute.call_args[0]
    assert "UPDATE notifiche SET Stato = 'letta'" in args[0]
    assert "12345" in args[1]
