"""
Test di sicurezza per il mercato dei turni (Bacheca).
Verifica l'integrità dei ruoli e dei permessi durante il subentro.
"""

import pytest
import streamlit as st
from modules.shifts.logic_market import prendi_turno_da_bacheca_logic

def test_aiutante_cannot_take_tecnico_shift(mocker):
    """Verifica che un Aiutante non possa tecnicamente prendere un turno da Tecnico."""
    # Mock annuncio bacheca che richiede un Tecnico
    mock_item = {
        "ID_Bacheca": "B1",
        "Stato": "Disponibile",
        "Ruolo_Originale": "Tecnico",
        "ID_Turno": "T1"
    }
    mocker.patch("modules.shifts.logic_market.get_bacheca_item_by_id", return_value=mock_item)
    
    # Simula utente Aiutante
    status = prendi_turno_da_bacheca_logic("MAT123", "Aiutante", "B1")
    
    assert status is False
    # Verifichiamo che venga mostrato un errore (mockando st.error)
    # Nota: la logica interna usa st.error
