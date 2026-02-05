"""
Test per gestione turni e limiti temporali.
"""

import datetime
import pandas as pd
from modules.shifts.logic_oncall import sync_oncall_shifts
from modules.database.db_shifts import get_shifts_by_type

def test_sync_oncall_year_change(mocker):
    """Verifica la rotazione dei turni tra 31/12 e 01/01."""
    start = datetime.date(2024, 12, 31)
    end = datetime.date(2025, 1, 1)
    
    mocker.patch("src.modules.shifts.logic_oncall.get_shifts_by_type", return_value=pd.DataFrame())
    mocker.patch("src.modules.shifts.logic_oncall.get_all_users", return_value=pd.DataFrame())
    mocker.patch("src.modules.shifts.logic_oncall.get_on_call_pair", return_value=(("A", "T"), ("B", "A")))
    mock_create = mocker.patch("src.modules.shifts.logic_oncall.create_shift", return_value=True)
    
    sync_oncall_shifts(start, end)
    
    # Deve aver creato 2 turni
    assert mock_create.call_count == 2

def test_get_shifts_by_invalid_type(mocker):
    """Verifica che un tipo turno inesistente non causi errori."""
    mocker.patch("src.core.database.DatabaseEngine.get_connection")
    # Simula un errore SQL o un tipo non trovato
    res = get_shifts_by_type("TIPO_INESISTENTE")
    assert isinstance(res, pd.DataFrame)
    assert res.empty
