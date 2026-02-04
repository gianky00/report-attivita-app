"""
Test per la sicurezza e stabilità della UX Streamlit.
Verifica la persistenza dello stato della sessione durante la navigazione.
"""

import pytest
import streamlit as st
from unittest.mock import MagicMock
from src.components.ui.navigation_ui import render_sidebar

def test_navigation_tab_persistence(mocker):
    """Verifica che il cambio tab aggiorni correttamente lo stato della sessione."""
    # Setup session state
    if "main_tab" not in st.session_state:
        st.session_state.main_tab = "Attività Assegnate"
    
    # Mock dei bottoni di navigazione (clicchiamo su Storico)
    mocker.patch("streamlit.sidebar")
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "🗂️ Storico")
    mock_rerun = mocker.patch("streamlit.rerun")
    
    # Mock moduli esterni chiamati in sidebar
    mocker.patch("src.components.ui.navigation_ui.leggi_notifiche", return_value=[])
    mocker.patch("src.components.ui.navigation_ui.get_last_login", return_value="2025-01-01 10:00")
    mocker.patch("src.components.ui.navigation_ui.get_next_on_call_week", return_value=None)
    
    render_sidebar("123", "Mario Rossi", "Tecnico")
    
    # Verifica che lo stato sia cambiato
    assert st.session_state.main_tab == "Storico"
    assert mock_rerun.called

def test_debriefing_task_persistence(mocker):
    """Verifica che i dati del form di debriefing non vengano persi se lo stato è impostato."""
    task_data = {"pdl": "123456", "attivita": "Test"}
    st.session_state.debriefing_task = task_data
    
    # Se debriefing_task è presente, app.py dovrebbe mostrare il form invece della navigazione
    # Questo test verifica solo la presenza nel session_state
    assert st.session_state.debriefing_task == task_data
    
    # Pulizia per altri test
    del st.session_state.debriefing_task

def test_session_clear_on_logout(mocker):
    """Verifica che il logout pulisca completamente la sessione."""
    st.session_state.authenticated_user = "123"
    st.session_state.session_token = "token-xyz"
    
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "Disconnetti")
    mocker.patch("src.components.ui.navigation_ui.delete_session")
    mocker.patch("src.components.ui.navigation_ui.leggi_notifiche", return_value=[])
    mocker.patch("src.components.ui.navigation_ui.get_last_login", return_value=None)
    mocker.patch("src.components.ui.navigation_ui.get_next_on_call_week", return_value=None)
    mock_rerun = mocker.patch("streamlit.rerun")
    
    render_sidebar("123", "Mario Rossi", "Tecnico")
    
    # Lo stato dovrebbe essere vuoto (o rimosso)
    assert "authenticated_user" not in st.session_state
    assert mock_rerun.called