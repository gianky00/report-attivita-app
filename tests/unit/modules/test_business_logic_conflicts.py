"""
Test per logica di business complessa e conflitti di disponibilità.
"""

import pandas as pd
import pytest
from modules.shifts.logic_bookings import prenota_turno_logic

def test_booking_conflict_with_oncall(mocker):
    """Verifica che un utente non possa prenotare un turno se è già in reperibilità in quel giorno."""
    # 1. Mock turno standard che si vuole prenotare
    mocker.patch("src.modules.shifts.logic_bookings.get_shift_by_id", 
                 return_value={"ID_Turno": "T1", "Data": "2025-01-01", "PostiTecnico": 1, "PostiAiutante": 1})
    
    # 2. Mock segnalazione conflitto (l'utente è già in reperibilità)
    mocker.patch("src.modules.shifts.logic_bookings.check_user_oncall_conflict", return_value=True)
    
    # Mockiamo st per evitare errori UI
    mock_st = mocker.patch("src.modules.shifts.logic_bookings.st")
    
    # Tentativo di prenotazione
    success = prenota_turno_logic("12345", "T1", "Tecnico")
    
    # Deve fallire a causa del conflitto
    assert success is False
    assert mock_st.error.called
    assert "Conflitto rilevato" in mock_st.error.call_args[0][0]

def test_booking_no_conflict_success(mocker):
    """Verifica che la prenotazione proceda se non ci sono conflitti."""
    mocker.patch("src.modules.shifts.logic_bookings.get_shift_by_id", 
                 return_value={"ID_Turno": "T1", "Data": "2025-01-01", "PostiTecnico": 1, "PostiAiutante": 1})
    
    # Nessun conflitto
    mocker.patch("src.modules.shifts.logic_bookings.check_user_oncall_conflict", return_value=False)
    
    # Nessuna prenotazione esistente (posti liberi), ma DataFrame con colonne corrette
    mock_empty_bookings = pd.DataFrame(columns=["Matricola", "RuoloOccupato"])
    mocker.patch("src.modules.shifts.logic_bookings.get_bookings_for_shift", return_value=mock_empty_bookings)
    
    # Successo salvataggio DB
    mocker.patch("src.modules.shifts.logic_bookings.add_booking", return_value=True)
    mocker.patch("src.modules.shifts.logic_bookings.log_shift_change")
    mocker.patch("src.modules.shifts.logic_bookings.st")
    
    success = prenota_turno_logic("12345", "T1", "Tecnico")
    
    assert success is True
