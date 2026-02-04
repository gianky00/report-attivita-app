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
    mocker.patch("streamlit.text_input", side_effect=["Mario", "Rossi", "123"])
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_error = mocker.patch("streamlit.error")
    
    # DF con utente già esistente
    df_contatti = pd.DataFrame([{"Matricola": "123", "Nome Cognome": "Esistente"}])
    
    _render_new_user_expander(df_contatti)
    
    assert mock_error.called
    assert "esiste già" in mock_error.call_args[0][0]

def test_user_creation_success(mocker):
    """Verifica il flusso di successo nella creazione di un utente."""
    mocker.patch("streamlit.expander")
    mocker.patch("streamlit.form")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("streamlit.text_input", side_effect=["Mario", "Rossi", "999"])
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    # Mocking create_user nel percorso reale
    mock_create = mocker.patch("src.pages.admin.users_view.create_user", return_value=True)
    
    # DF vuoto
    df_contatti = pd.DataFrame(columns=["Matricola", "Nome Cognome"])
    
    _render_new_user_expander(df_contatti)
    
    assert mock_create.called
    assert mock_success.called
    assert "creato" in mock_success.call_args[0][0]

def test_user_deletion_confirmation(mocker):
    """Verifica che la cancellazione richieda conferma."""
    user = {"Matricola": "123", "Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico"}
    st.session_state.deleting_user_matricola = "123"
    
    mocker.patch("streamlit.container")
    # Qui il codice chiama st.columns([3, 1]) e poi st.columns(3)
    # Dobbiamo gestire entrambe le chiamate o patchare con flessibilità
    mock_cols = [mocker.MagicMock() for _ in range(3)]
    mocker.patch("streamlit.columns", return_value=mock_cols)
    
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "✅ Conferma Eliminazione")
    mock_warning = mocker.patch("streamlit.warning")
    mock_delete = mocker.patch("src.pages.admin.users_view.delete_user", return_value=True)
    mocker.patch("streamlit.rerun")
    
    _render_user_card(user)
    
    assert mock_warning.called
    assert mock_delete.called
