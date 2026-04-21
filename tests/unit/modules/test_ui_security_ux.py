"""
Test unitari per l'esperienza utente legata alla sicurezza (Navigazione, Sessioni).
"""

import pandas as pd
import streamlit as st
from components.ui.navigation_ui import render_sidebar

def test_navigation_tab_persistence(mocker):
    """Verifica che il cambio tab aggiorni correttamente lo stato della sessione."""
    if "main_tab" not in st.session_state:
        st.session_state.main_tab = "Attività Assegnate"

    mocker.patch("streamlit.sidebar")
    mocker.patch("streamlit.image")
    mocker.patch("streamlit.divider")
    
    # Mock dei bottoni per simulare il click su Storico.
    # Usiamo key per identificare i bottoni
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: kwargs.get("key") == "nav_history")
    mock_rerun = mocker.patch("streamlit.rerun")

    # Mock moduli esterni
    mocker.patch("components.ui.navigation_ui.leggi_notifiche", return_value=pd.DataFrame())
    mocker.patch("components.ui.navigation_ui.render_notification_center")
    mocker.patch("components.ui.navigation_ui.get_next_on_call_week", return_value=None)

    render_sidebar("M1", "Mario Rossi", "Tecnico")

    assert st.session_state.main_tab == "Storico"
    assert mock_rerun.called

def test_session_clear_on_logout(mocker):
    """Verifica che il logout pulisca completamente la sessione."""
    st.session_state.authenticated_user = "123"
    st.session_state.session_token = "token-xyz"

    mocker.patch("streamlit.sidebar")
    mocker.patch("streamlit.image")
    mocker.patch("streamlit.divider")
    
    # Simula click su Logout
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: kwargs.get("key") == "nav_logout")
    mock_delete = mocker.patch("components.ui.navigation_ui.delete_session")
    mocker.patch("streamlit.query_params", mocker.MagicMock())
    mock_rerun = mocker.patch("streamlit.rerun")
    
    # Mock necessari per il resto della funzione
    mocker.patch("components.ui.navigation_ui.leggi_notifiche", return_value=pd.DataFrame())
    mocker.patch("components.ui.navigation_ui.render_notification_center")
    mocker.patch("components.ui.navigation_ui.get_next_on_call_week", return_value=None)

    render_sidebar("123", "User", "Tecnico")

    assert mock_delete.called
    assert "authenticated_user" not in st.session_state
    assert mock_rerun.called
