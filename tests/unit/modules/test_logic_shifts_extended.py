"""
Test unitari estesi per la logica dei turni (prenotazioni e bacheca).
Copre limiti di prenotazione e permessi bacheca.
"""

import pandas as pd
import pytest
import datetime
from modules.shifts.logic_bookings import prenota_turno_logic
from modules.shifts.logic_market import (
    pubblica_turno_in_bacheca_logic,
    prendi_turno_da_bacheca_logic,
)

def test_prenota_turno_limit_reached(mocker):
    """Verifica che la prenotazione fallisca se il limite di posti è raggiunto."""
    # Mock turno con 1 posto Tecnico
    mocker.patch("modules.shifts.logic_bookings.get_shift_by_id", 
                 return_value={
                     "ID_Turno": "T1", 
                     "PostiTecnico": 1, 
                     "PostiAiutante": 0,
                     "Data": datetime.date.today().isoformat()
                 })
    
    # Mock 1 prenotazione già esistente come Tecnico
    mock_bookings = pd.DataFrame([{"Matricola": "999", "RuoloOccupato": "Tecnico"}])
    mocker.patch("modules.shifts.logic_bookings.get_bookings_for_shift", return_value=mock_bookings)
    mocker.patch("modules.shifts.logic_bookings.check_user_oncall_conflict", return_value=False)
    mocker.patch("modules.shifts.logic_bookings.st")
    
    # Tentativo di prenotazione (dovrebbe fallire)
    success = prenota_turno_logic("123", "T1", "Tecnico")
    assert success is False

def test_pubblica_in_bacheca_success(mocker):
    """Verifica la pubblicazione di un turno in bacheca."""
    # Mock prenotazione esistente
    mock_booking = {"ID_Prenotazione": "P1", "RuoloOccupato": "Tecnico"}
    mocker.patch("modules.shifts.logic_market.get_booking_by_user_and_shift", return_value=mock_booking)
    
    # Mock DB transaction
    mock_conn = mocker.patch("modules.shifts.logic_market.get_db_connection")
    mocker.patch("modules.shifts.logic_market.add_bacheca_item", return_value=True)
    mocker.patch("modules.shifts.logic_market.log_shift_change")
    mocker.patch("modules.shifts.logic_market.get_shift_by_id", return_value=None)
    mocker.patch("modules.shifts.logic_market.st")
    
    success = pubblica_turno_in_bacheca_logic("123", "T1")
    assert success is True

def test_prendi_da_bacheca_role_mismatch(mocker):
    """Verifica che un Aiutante non possa prendere un turno da Tecnico in bacheca."""
    # Mock annuncio bacheca per Tecnico
    mock_item = {"ID_Turno": "T1", "Stato": "Disponibile", "Ruolo_Originale": "Tecnico"}
    mocker.patch("modules.shifts.logic_market.get_bacheca_item_by_id", return_value=mock_item)
    
    mocker.patch("modules.shifts.logic_market.st")
    
    # Tentativo da parte di un Aiutante
    success = prendi_turno_da_bacheca_logic("123", "Aiutante", "B1")
    assert success is False