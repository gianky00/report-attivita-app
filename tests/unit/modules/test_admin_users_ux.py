"""
Test per i flussi UX di amministrazione utenti.
"""

import pytest
import streamlit as st
import pandas as pd
from src.pages.admin.users_view import _render_new_user_expander, _render_user_card

def test_user_creation_duplicate_error(mocker):
    """Verifica che la creazione di un utente con matricola duplicata mostri un errore."""
    mocker.patch("streamlit.expander")
    mocker.patch("streamlit.form")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    
    # Ritorna sempre "123" per tutti i text_input per forzare il duplicato
    mocker.patch("streamlit.text_input", return_value="123")
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    
    mock_error = mocker.patch("streamlit.error")
    # Patchiamo create_user nel modulo auth (dove viene importato)
    mock_create = mocker.patch("src.pages.admin.users_view.create_user")
    
    # Prepariamo un DF con vari tipi di matricola per sicurezza
    df_contatti = pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Esistente String"},
        {"Matricola": 123, "Nome Cognome": "Esistente Int"}
    ])
    
    _render_new_user_expander(df_contatti)
    
    assert not mock_create.called, "create_user non dovrebbe essere chiamato per un duplicato"
    assert mock_error.called

def test_user_creation_success(mocker):
    """Verifica il flusso di successo nella creazione di un utente."""
    mocker.patch("streamlit.expander")
    mocker.patch("streamlit.form")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("streamlit.text_input", return_value="999")
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    mocker.patch("src.pages.admin.users_view.create_user", return_value=True)
    
    df_contatti = pd.DataFrame(columns=["Matricola", "Nome Cognome"])
    _render_new_user_expander(df_contatti)
    
    assert mock_success.called

def test_user_deletion_confirmation(mocker):
    """Verifica che la cancellazione richieda conferma."""
    user = {"Matricola": "123", "Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico"}
    st.session_state.deleting_user_matricola = "123"
    
    mocker.patch("streamlit.container")
    
    def mock_cols(spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [mocker.MagicMock() for _ in range(n)]
    
    mocker.patch("streamlit.columns", side_effect=mock_cols)
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "✅ Conferma Eliminazione")
    mock_warning = mocker.patch("streamlit.warning")
    mocker.patch("src.pages.admin.users_view.delete_user", return_value=True)
    mocker.patch("streamlit.rerun")
    
    _render_user_card(user)
    
    assert mock_warning.called
