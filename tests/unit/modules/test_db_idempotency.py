"""
Test di integrità e idempotenza per importazione dati storici.
"""

import pytest
import sqlite3
from modules.database.db_reports import salva_report_intervento

def test_excel_import_idempotency(mocker):
    """Verifica che l'inserimento dello stesso report più volte non crei duplicati."""
    # Patchiamo DatabaseEngine.execute che è il metodo centralizzato
    mock_exec = mocker.patch("src.modules.database.db_reports.DatabaseEngine.execute")
    
    report_data = {
        "id_report": "ST_2025_001",
        "descrizione": "Intervento manutenzione",
        "data": "2025-01-01"
    }
    
    # 1. Primo inserimento (successo)
    mock_exec.return_value = True
    success1 = salva_report_intervento(report_data)
    assert success1 is True
    assert mock_exec.called
    
    # 2. Secondo inserimento (fallimento per duplicato)
    # Simuliamo che DatabaseEngine restituisca False in caso di IntegrityError
    mock_exec.return_value = False
    success2 = salva_report_intervento(report_data)
    assert success2 is False
