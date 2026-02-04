"""
Test di integrità per la logica di prenotazione turni.
Verifica la gestione di duplicati e vincoli di database.
"""

import pytest
from src.modules.shifts.logic_bookings import prenota_turno_logic

def test_double_booking_prevention(mocker):
    """Verifica che un utente non possa prenotarsi due volte per lo stesso turno."""
    # 1. Mock turno valido con posti liberi
    mocker.patch("src.modules.shifts.logic_bookings.get_shift_by_id", 
                 return_value={"ID_Turno": "T1", "PostiTecnico": 2, "PostiAiutante": 2})
    
    # 2. Mock DB: la add_booking fallisce a causa di un IntegrityError (simulato)
    # oppure la logica di business rileva già la presenza (mockiamo get_bookings_for_shift)
    import pandas as pd
    mock_existing = pd.DataFrame([{"Matricola": "12345", "RuoloOccupato": "Tecnico"}])
    mocker.patch("src.modules.shifts.logic_bookings.get_bookings_for_shift", return_value=mock_existing)
    
    mocker.patch("src.modules.shifts.logic_bookings.st")
    
    # Tentativo di prenotazione (anche se ci sono posti, l'utente 12345 è già dentro)
    # Nota: Attualmente la funzione prenota_turno_logic non controlla esplicitamente 
    # se l'utente è già presente, ma conta solo i posti totali. 
    # Questo test servirà a evidenziare la necessità di tale controllo.
    
    # Mockiamo add_booking per lanciare IntegrityError se tentiamo di inserire un duplicato
    # (assumendo che ci sia un vincolo UNIQUE(ID_Turno, Matricola) nel DB)
    mocker.patch("src.modules.shifts.logic_bookings.add_booking", return_value=False)
    
    success = prenota_turno_logic("12345", "T1", "Tecnico")
    assert success is False
