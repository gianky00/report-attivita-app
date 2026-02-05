"""
Test unitari per il form delle relazioni reperibilità.
Copre src/components/forms/relazione_oncall_form.py.
"""

import datetime
import pytest
import pandas as pd
import streamlit as st
from components.forms.relazione_oncall_form import render_relazione_reperibilita_ui

class MockSessionState(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: raise AttributeError(key)
    def __setattr__(self, key, value): self[key] = value
    def __delattr__(self, key):
        try: del self[key]
        except KeyError: raise AttributeError(key)

def test_render_relazione_reperibilita_ui_success(mocker):
    session = MockSessionState({"relazione_testo": "Testo"})
    mocker.patch("streamlit.session_state", session)
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.caption")
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    
    # Smart mock for columns: returns 2 or 3 mocks depending on input
    mocker.patch("streamlit.columns", side_effect=lambda spec: [mocker.MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))])
    
    mocker.patch("streamlit.text_input", return_value="User")
    mocker.patch("streamlit.selectbox", return_value="Nessuno")
    mocker.patch("streamlit.date_input", return_value=datetime.date.today())
    mocker.patch("streamlit.text_area", return_value="Contenuto")
    
    # Simulate clicking "Invia"
    mocker.patch("streamlit.form_submit_button", side_effect=[False, False, True])
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    df_users = pd.DataFrame([{"Matricola": "M2", "Nome Cognome": "Partner"}])
    mocker.patch("components.forms.relazione_oncall_form.get_all_users", return_value=df_users)
    mocker.patch("components.forms.relazione_oncall_form.salva_relazione", return_value=True)
    mocker.patch("components.forms.relazione_oncall_form.invia_email_con_outlook_async")
    
    render_relazione_reperibilita_ui("M1", "User")
    assert st.success.called

def test_handle_ai_correction(mocker):
    from components.forms.relazione_oncall_form import _handle_ai_correction
    mocker.patch("streamlit.spinner", return_value=mocker.MagicMock())
    session = MockSessionState({})
    mocker.patch("streamlit.session_state", session)
    mocker.patch("components.forms.relazione_oncall_form.revisiona_con_ia", return_value={"success": True, "text": "Revised"})
    mocker.patch("streamlit.success")
    
    _handle_ai_correction("Original")
    assert session.relazione_revisionata == "Revised"
