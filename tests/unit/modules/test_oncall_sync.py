"""
Test per la logica dei turni di reperibilità settimanale.
"""

import datetime
import pandas as pd
from src.modules.shifts.logic_oncall import sync_oncall_shifts

def test_sync_oncall_shifts_no_changes(mocker):
    """Verifica che non vengano creati turni se già presenti."""
    today = datetime.date(2025, 1, 1)
    df_turni = pd.DataFrame([{"Data": "2025-01-01", "Tipo": "Reperibilità"}])
    
    mocker.patch("src.modules.shifts.logic_oncall.get_shifts_by_type", return_value=df_turni)
    mocker.patch("src.modules.shifts.logic_oncall.get_all_users", return_value=pd.DataFrame())
    
    changed = sync_oncall_shifts(today, today)
    assert changed is False

def test_sync_oncall_shifts_creation(mocker):
    """Verifica la creazione automatica di un turno mancante."""
    today = datetime.date(2025, 1, 1)
    mocker.patch("src.modules.shifts.logic_oncall.get_shifts_by_type", return_value=pd.DataFrame())
    mocker.patch("src.modules.shifts.logic_oncall.get_all_users", return_value=pd.DataFrame())
    mocker.patch("src.modules.shifts.logic_oncall.get_on_call_pair", return_value=(("R", "T"), ("G", "A")))
    mocker.patch("src.modules.shifts.logic_oncall.create_shift", return_value=True)
    
    changed = sync_oncall_shifts(today, today)
    assert changed is True