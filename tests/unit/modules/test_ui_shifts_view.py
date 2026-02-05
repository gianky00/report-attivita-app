"""
Test unitari per la creazione di nuovi turni.
Copre src/pages/admin/shifts_view.py.
"""

import datetime
import pytest
import pandas as pd
import streamlit as st
from pages.admin.shifts_view import render_new_shift_form

def test_render_new_shift_form_success(mocker):
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.selectbox", return_value="Assistenza")
    mocker.patch("streamlit.text_input", return_value="Test Shift")
    mocker.patch("streamlit.date_input", return_value=datetime.date.today())
    mocker.patch("streamlit.time_input", return_value=datetime.time(8, 0))
    mocker.patch("streamlit.number_input", return_value=1)
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock() for _ in range(2)])
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    # Patch local references
    mocker.patch("pages.admin.shifts_view.create_shift", return_value=True)
    mocker.patch("pages.admin.shifts_view.get_all_users", return_value=pd.DataFrame([{"Matricola": "123"}]))
    mocker.patch("pages.admin.shifts_view.crea_notifica", return_value=True)
    
    render_new_shift_form()
    assert mock_success.called

def test_render_new_shift_form_missing_desc(mocker):
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    mocker.patch("streamlit.text_input", return_value="")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_error = mocker.patch("streamlit.error")
    
    render_new_shift_form()
    assert mock_error.called
