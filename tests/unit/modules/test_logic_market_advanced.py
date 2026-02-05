"""
Test unitari avanzati per la logica di mercato (logic_market.py).
Focalizzato sulla risposta alle sostituzioni e transazioni bacheca.
"""

import pytest
import sqlite3
from modules.shifts.logic_market import (
    rispondi_sostituzione_logic,
    pubblica_turno_in_bacheca_logic,
    prendi_turno_da_bacheca_logic
)

@pytest.fixture
def mock_st_shifts(mocker):
    """Mock di streamlit per i test dei turni."""
    return mocker.patch("modules.shifts.logic_market.st")

def test_rispondi_sostituzione_accettata(mocker, mock_st_shifts):
    """Verifica il ciclo completo di accettazione sostituzione."""
    # 1. Mock richiesta esistente
    mock_req = {"ID_Richiesta": "R1", "Richiedente_Matricola": "M1", "ID_Turno": "T1"}
    mocker.patch("modules.shifts.logic_market.get_substitution_request_by_id", return_value=mock_req)
    mocker.patch("modules.shifts.logic_market.get_user_by_matricola", return_value={"Nome Cognome": "User"})
    mocker.patch("modules.shifts.logic_market.delete_substitution_request", return_value=True)
    mocker.patch("modules.shifts.logic_market.crea_notifica")
    
    # 2. Mock successo subentro
    mocker.patch("modules.shifts.logic_market.update_booking_user", return_value=True)
    mocker.patch("modules.shifts.logic_market.log_shift_change")
    
    success = rispondi_sostituzione_logic("R1", "M2", accettata=True)
    
    assert success is True
    assert mock_st_shifts.success.called

def test_rispondi_sostituzione_rifiutata(mocker, mock_st_shifts):
    """Verifica il ciclo di rifiuto sostituzione."""
    mock_req = {"ID_Richiesta": "R1", "Richiedente_Matricola": "M1", "ID_Turno": "T1"}
    mocker.patch("modules.shifts.logic_market.get_substitution_request_by_id", return_value=mock_req)
    mocker.patch("modules.shifts.logic_market.delete_substitution_request", return_value=True)
    mocker.patch("modules.shifts.logic_market.crea_notifica")
    mocker.patch("modules.shifts.logic_market.get_user_by_matricola", return_value=None)
    
    success = rispondi_sostituzione_logic("R1", "M2", accettata=False)
    
    assert success is True
    assert mock_st_shifts.info.called

def test_pubblica_bacheca_db_error(mocker, mock_st_shifts):
    """Verifica la gestione errore DB durante la pubblicazione in bacheca."""
    mocker.patch("modules.shifts.logic_market.get_booking_by_user_and_shift", return_value={"ID_Prenotazione": "P1", "RuoloOccupato": "Tecnico"})
    
    # Simula errore sqlite3 nella transazione
    mock_conn = mocker.patch("modules.shifts.logic_market.get_db_connection")
    mock_conn.side_effect = sqlite3.Error("Transaction failed")
    
    success = pubblica_turno_in_bacheca_logic("M1", "T1")
    
    assert success is False
    assert mock_st_shifts.error.called

def test_prendi_turno_non_disponibile(mocker, mock_st_shifts):
    """Verifica che non si possa prendere un turno già assegnato."""
    mocker.patch("modules.shifts.logic_market.get_bacheca_item_by_id", return_value={"Stato": "Assegnato"})
    
    success = prendi_turno_da_bacheca_logic("M1", "Tecnico", "B1")
    assert success is False
    assert mock_st_shifts.error.called
