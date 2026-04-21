"""
Test unitari per l'importer dei file Excel Giornaliera.
"""

import pandas as pd
import pytest
from modules.importers.excel_giornaliera import trova_attivita

@pytest.fixture
def mock_df_contatti():
    return pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico"},
        {"Matricola": "456", "Nome Cognome": "Luigi Bianchi", "Ruolo": "Aiutante"}
    ])

def test_trova_attivita_no_sheet(mocker, mock_df_contatti):
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=None)
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    assert res == []

def test_trova_attivita_parsing_success(mocker, mock_df_contatti):
    data = {
        5: ["Rossi M.", "Bianchi L."],
        6: ["Sostituzione Valvola\nTest", "Sostituzione Valvola"],
        9: ["123456", "123456"],
        10: ["08:00", "08:00"],
        11: ["12:00", "12:00"],
    }
    df_sheet = pd.DataFrame(data)
    for i in range(15):
        if i not in df_sheet.columns:
            df_sheet[i] = ""
            
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=df_sheet)
    # Mock solo per la funzione realmente importata nel modulo
    mocker.patch("modules.importers.excel_giornaliera.get_excluded_activities_for_user", return_value=[])
    
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    assert len(res) == 1
    assert res[0]["pdl"] == "123456"

def test_trova_attivita_malformed_data(mocker, mock_df_contatti):
    data = {
        5: [None, "Rossi M."],
        6: ["Test", "Valid"],
        9: ["123456", "654321"],
        10: ["08:00", "08:00"],
        11: ["12:00", "12:00"],
    }
    df_sheet = pd.DataFrame(data)
    for i in range(15):
        if i not in df_sheet.columns:
            df_sheet[i] = ""
            
    mocker.patch("modules.importers.excel_giornaliera._load_day_sheet", return_value=df_sheet)
    mocker.patch("modules.importers.excel_giornaliera.get_excluded_activities_for_user", return_value=[])
    
    res = trova_attivita("123", 1, 1, 2025, mock_df_contatti)
    assert len(res) == 1
    assert res[0]["pdl"] == "654321"
