"""
Test per la sicurezza e stabilità della UX Streamlit.
Verifica la persistenza dello stato della sessione durante la navigazione.
"""

import pytest
import streamlit as st
import pandas as pd
from components.ui.navigation_ui import render_sidebar

def test_navigation_tab_persistence(mocker):
    """Verifica che il cambio tab aggiorni correttamente lo stato della sessione."""
    if "main_tab" not in st.session_state:
        st.session_state.main_tab = "Attività Assegnate"
    
    mocker.patch("streamlit.sidebar")
    # Mock dei bottoni per simulare il click su Storico
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "🗂️ Storico")
    mock_rerun = mocker.patch("streamlit.rerun")
    
    # Mock moduli esterni
    mocker.patch("components.ui.navigation_ui.leggi_notifiche", return_value=pd.DataFrame(columns=["Stato"]))
    mocker.patch("components.ui.navigation_ui.get_last_login", return_value="2025-01-01 10:00")
    mocker.patch("components.ui.navigation_ui.get_next_on_call_week", return_value=None)
    
    render_sidebar("123", "Mario Rossi", "Tecnico")
    
    assert st.session_state.main_tab == "Storico"
    assert mock_rerun.called

def test_session_clear_on_logout(mocker):
    """Verifica che il logout pulisca completamente la sessione."""
    st.session_state.authenticated_user = "123"
    st.session_state.session_token = "token-xyz"
    
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "Disconnetti")
    mocker.patch("components.ui.navigation_ui.delete_session")
    mocker.patch("components.ui.navigation_ui.leggi_notifiche", return_value=pd.DataFrame(columns=["Stato"]))
    mocker.patch("components.ui.navigation_ui.get_last_login", return_value=None)
    mocker.patch("components.ui.navigation_ui.get_next_on_call_week", return_value=None)
    mock_rerun = mocker.patch("streamlit.rerun")
    
    render_sidebar("123", "Mario Rossi", "Tecnico")
    
    assert "authenticated_user" not in st.session_state
    assert mock_rerun.called
