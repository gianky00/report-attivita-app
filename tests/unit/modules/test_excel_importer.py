"""
Test per il parsing robusto dei file Excel Giornaliera.
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock, patch
from modules.importers.excel_giornaliera import trova_attivita

@pytest.fixture
def mock_df_contatti():
    return pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico"},
        {"Matricola": "456", "Nome Cognome": "Luigi Bianchi", "Ruolo": "Aiutante"}
    ])

def test_trova_attivita_no_sheet(mocker, mock_df_contatti):
    """Verifica che la funzione gestisca l'assenza del foglio excel senza crashare."""
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=None)
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    assert res == []

def test_trova_attivita_parsing_success(mocker, mock_df_contatti):
    """Verifica l'estrazione corretta dei dati da un DataFrame simulato."""
    # Creiamo un DataFrame che simula la struttura del foglio excel
    # r[5] = Nome, r[9] = PdL, r[6] = Descrizione, r[10] = Inizio, r[11] = Fine
    data = {
        5: ["Rossi M.", "Bianchi L."],
        6: ["Sostituzione Valvola\nTest", "Sostituzione Valvola"],
        9: ["123456", "123456"],
        10: ["08:00", "08:00"],
        11: ["12:00", "12:00"]
    }
    df_sheet = pd.DataFrame(data)
    # Riempie le colonne mancanti per evitare index out of range
    for i in range(15):
        if i not in df_sheet.columns: df_sheet[i] = ""
        
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=df_sheet)
    mocker.patch("modules.importers.excel_giornaliera.get_globally_excluded_activities", return_value=[])
    
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    
    assert len(res) > 0
    assert res[0]["pdl"] == "123456"
    assert "Valvola" in res[0]["attivita"]
    # Verifica che il team includa entrambi i tecnici assegnati allo stesso PdL
    assert len(res[0]["team"]) == 2

def test_trova_attivita_malformed_data(mocker, mock_df_contatti):
    """Verifica la resilienza a righe incomplete o dati mancanti."""
    data = {
        5: [None, "Rossi M."], # Nome mancante nella prima riga
        6: ["Test", "Valid"],
        9: ["123456", "654321"],
        10: ["08:00", "08:00"],
        11: ["12:00", "12:00"]
    }
    df_sheet = pd.DataFrame(data)
    for i in range(15):
        if i not in df_sheet.columns: df_sheet[i] = ""
        
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=df_sheet)
    mocker.patch("modules.importers.excel_giornaliera.get_globally_excluded_activities", return_value=[])
    
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    # Deve comunque processare la riga valida
    assert any(a["pdl"] == "654321" for a in res)