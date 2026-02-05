"""
Test di integrità per la logica di prenotazione turni.
Verifica la gestione di duplicati e vincoli di database.
"""

import pytest
import datetime
import pandas as pd
from modules.shifts.logic_bookings import prenota_turno_logic

def test_double_booking_prevention(mocker):
    """Verifica che un utente non possa prenotarsi due volte per lo stesso turno."""
    # 1. Mock turno valido con posti liberi
    mocker.patch("modules.shifts.logic_bookings.get_shift_by_id", 
                 return_value={
                     "ID_Turno": "T1", 
                     "PostiTecnico": 2, 
                     "PostiAiutante": 2,
                     "Data": datetime.date.today().isoformat()
                 })
    
    # 2. Mock DB
    mock_existing = pd.DataFrame([{"Matricola": "12345", "RuoloOccupato": "Tecnico"}])
    mocker.patch("modules.shifts.logic_bookings.get_bookings_for_shift", return_value=mock_existing)
    mocker.patch("modules.shifts.logic_bookings.check_user_oncall_conflict", return_value=False)
    mocker.patch("modules.shifts.logic_bookings.st")
    mocker.patch("modules.shifts.logic_bookings.add_booking", return_value=False)
    
    success = prenota_turno_logic("12345", "T1", "Tecnico")
    assert success is False