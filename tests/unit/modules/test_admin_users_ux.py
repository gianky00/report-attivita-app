"""
Test per i flussi UX di amministrazione utenti.
"""

import pytest
import streamlit as st
import pandas as pd
from pages.admin.users_view import _render_new_user_expander, _render_user_card

def test_user_creation_duplicate_error(mocker):
    """Verifica che la creazione di un utente con matricola duplicata mostri un errore."""
    # Configurazione Context Managers
    mock_expander = mocker.MagicMock()
    mock_expander.__enter__.return_value = mock_expander
    mocker.patch("streamlit.expander", return_value=mock_expander)
    
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    
    # Mock Colonne e loro widget
    mock_c1 = mocker.MagicMock()
    mock_c2 = mocker.MagicMock()
    mock_c3 = mocker.MagicMock()
    mock_c4 = mocker.MagicMock()
    
    # Configurazione side_effect per tornare le coppie di colonne in sequenza
    mocker.patch("streamlit.columns", side_effect=[[mock_c1, mock_c2], [mock_c3, mock_c4]])
    
    # Widget delle colonne
    mock_c1.text_input.return_value = "Mario"
    mock_c2.text_input.return_value = "Rossi"
    mock_c3.text_input.return_value = "123"
    mock_c4.selectbox.return_value = "Tecnico"
    
    mocker.patch("streamlit.form_submit_button", return_value=True)
    
    mock_error = mocker.patch("streamlit.error")
    # Patchiamo create_user nel modulo auth (dove viene importato)
    mock_create = mocker.patch("pages.admin.users_view.create_user")
    
    # Prepariamo un DF con la matricola "123" come stringa, senza spazi
    df_contatti = pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Esistente"}
    ])
    
    _render_new_user_expander(df_contatti)
    
    assert mock_error.called, "st.error dovrebbe essere chiamato per matricola duplicata"
    assert not mock_create.called, "create_user non dovrebbe essere chiamato per un duplicato"

def test_user_creation_success(mocker):
    """Verifica il flusso di successo nella creazione di un utente."""
    mocker.patch("streamlit.expander")
    mocker.patch("streamlit.form")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    
    # In questo test semplificato, facciamo tornare valori che NON sono nel DF
    mocker.patch("streamlit.text_input", return_value="999")
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    mocker.patch("pages.admin.users_view.create_user", return_value=True)
    
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
    mocker.patch("pages.admin.users_view.delete_user", return_value=True)
    mocker.patch("streamlit.rerun")
    
    _render_user_card(user)
    
    assert mock_warning.called

def test_render_gestione_account_search(mocker):
    from pages.admin.users_view import render_gestione_account
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.text_input", return_value="Mario")
    mocker.patch("streamlit.container")
    
    def mock_cols(spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [mocker.MagicMock() for _ in range(n)]
    mocker.patch("streamlit.columns", side_effect=mock_cols)
    
    mocker.patch("streamlit.button")
    mocker.patch("streamlit.markdown")
    
    df = pd.DataFrame([
        {"Matricola": "123", "Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico", "PasswordHash": "H", "2FA_Secret": "S"}
    ])
    mocker.patch("pages.admin.users_view.get_all_users", return_value=df)
    
    render_gestione_account()
    assert True
