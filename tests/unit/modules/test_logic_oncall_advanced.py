"""
Test unitari per la logica di reperibilità (logic_oncall.py).
Focalizzato sulla sincronizzazione dei turni e override manuali.
"""

import datetime
import pytest
import sqlite3
import pandas as pd
from src.modules.shifts.logic_oncall import sync_oncall_shifts, manual_override_logic

@pytest.fixture
def mock_st_oncall(mocker):
    """Mock di streamlit per i test di reperibilità."""
    return mocker.patch("src.modules.shifts.logic_oncall.st")

def test_sync_oncall_shifts_new_dates(mocker, mock_st_oncall):
    """Verifica la creazione di nuovi turni se le date non sono presenti."""
    # Mock turni esistenti (vuoti)
    mocker.patch("src.modules.shifts.logic_oncall.get_shifts_by_type", return_value=pd.DataFrame())
    # Mock utenti
    mock_users = pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "ROSSI MARIO", "Cognome": "ROSSI"}])
    mocker.patch("src.modules.shifts.logic_oncall.get_all_users", return_value=mock_users)
    
    # Mock coppia reperibilità
    mocker.patch("src.modules.shifts.logic_oncall.get_on_call_pair", return_value=(("ROSSI", "Tecnico"), ("BIANCHI", "Aiutante")))
    
    # Mock funzioni DB
    mocker.patch("src.modules.shifts.logic_oncall.create_shift", return_value=True)
    mocker.patch("src.modules.shifts.logic_oncall.add_booking", return_value=True)
    mocker.patch("src.modules.shifts.logic_oncall.find_matricola_by_surname", side_effect=["M1", None])
    
    start_date = datetime.date(2025, 1, 1)
    end_date = datetime.date(2025, 1, 1) # Solo 1 giorno
    
    changes = sync_oncall_shifts(start_date, end_date)
    
    assert changes is True
    assert mock_st_oncall.warning.called # Bianchi non trovato

def test_manual_override_logic_success(mocker, mock_st_oncall):
    """Verifica il successo della sovrascrittura manuale dei turni."""
    mock_conn = mocker.patch("src.modules.shifts.logic_oncall.get_db_connection")
    mock_cursor = mock_conn.return_value.cursor.return_value
    
    mocker.patch("src.modules.shifts.logic_oncall.get_user_by_matricola", return_value={"Ruolo": "Tecnico"})
    mocker.patch("src.modules.shifts.logic_oncall.log_shift_change")
    
    success = manual_override_logic("REP_T1", "M1", "M2", "ADMIN1")
    
    assert success is True
    assert mock_conn.return_value.commit.called

def test_manual_override_logic_db_error(mocker, mock_st_oncall):
    """Verifica la gestione errore (rollback) durante l'override manuale."""
    mock_conn = mocker.patch("src.modules.shifts.logic_oncall.get_db_connection")
    mock_conn.return_value.execute.side_effect = sqlite3.Error("Transaction error")
    
    success = manual_override_logic("REP_T1", "M1", "M2", "ADMIN1")
    
    assert success is False
    assert mock_conn.return_value.rollback.called
    assert mock_st_oncall.error.called
