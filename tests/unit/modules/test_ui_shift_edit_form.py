"""
Test unitari per la modifica dei turni.
Copre src/components/forms/shift_edit_form.py.
"""

import pytest
import pandas as pd
import streamlit as st
from components.forms.shift_edit_form import render_edit_shift_form

def test_render_edit_shift_form_success(mocker):
    mocker.patch("streamlit.session_state", {"editing_turno_id": "T1", "authenticated_user": "admin"})
    mocker.patch("streamlit.subheader")
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    mocker.patch("streamlit.text_input", return_value="Desc")
    mocker.patch("streamlit.selectbox", return_value="Reperibilità")
    mocker.patch("streamlit.multiselect", return_value=[])
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock() for _ in range(3)])
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    mocker.patch("components.forms.shift_edit_form.get_shift_by_id", return_value={"Descrizione": "Old"})
    mocker.patch("components.forms.shift_edit_form.get_bookings_for_shift", return_value=pd.DataFrame(columns=["Matricola", "RuoloOccupato"]))
    mocker.patch("components.forms.shift_edit_form.get_all_users", return_value=pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "U1"}]))
    mocker.patch("components.forms.shift_edit_form.update_shift", return_value=True)
    
    render_edit_shift_form()
    assert st.success.called

def test_render_edit_shift_form_missing_id(mocker):
    mocker.patch("streamlit.session_state", {})
    mock_err = mocker.patch("streamlit.error")
    render_edit_shift_form()
    assert mock_err.called
