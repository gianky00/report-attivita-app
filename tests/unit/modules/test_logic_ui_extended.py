"""
Test estesi per la logica di rendering dei componenti UI.
"""

import pytest
import streamlit as st
import pandas as pd
from components.ui.activity_ui import disegna_sezione_attivita, visualizza_storico_organizzato

def test_disegna_sezione_attivita_empty(mocker):
    """Verifica il rendering con lista attività vuota."""
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("components.ui.activity_ui.get_unvalidated_reports_by_technician", return_value=pd.DataFrame())
    
    disegna_sezione_attivita([], "empty_sec", "Tecnico")
    
    assert mock_success.called
    assert "compilate" in mock_success.call_args[0][0]

def test_visualizza_storico_large_dataset(mocker):
    """Verifica che lo storico gestisca dataset numerosi senza crashare."""
    mocker.patch("streamlit.expander")
    mock_toggle = mocker.patch("streamlit.toggle", return_value=False)
    
    storico = [
        {"Data_Riferimento_dt": "2025-01-01", "Tecnico": "T1", "Report": "Ok"}
        for _ in range(50)
    ]
    
    visualizza_storico_organizzato(storico, "123456")
    assert mock_toggle.call_count == 50

def test_disegna_sezione_attivita_role_check(mocker):
    """Verifica che un Aiutante non possa compilare report di team."""
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.divider")
    mocker.patch("components.ui.activity_ui.get_unvalidated_reports_by_technician", return_value=pd.DataFrame())
    mock_warning = mocker.patch("streamlit.warning")
    
    attivita = [{
        "pdl": "123456", 
        "attivita": "Test Team", 
        "team": [
            {"nome": "T1", "ruolo": "Tecnico", "orari": ["08:00-12:00"]}, 
            {"nome": "T2", "ruolo": "Tecnico", "orari": ["08:00-12:00"]}
        ]
    }]
    
    mocker.patch("streamlit.expander")
    mocker.patch("components.ui.activity_ui.merge_time_slots", return_value=["08:00-12:00"])
    
    disegna_sezione_attivita(attivita, "role_sec", "Aiutante")
    
    assert mock_warning.called
    assert "Solo i tecnici" in mock_warning.call_args[0][0]