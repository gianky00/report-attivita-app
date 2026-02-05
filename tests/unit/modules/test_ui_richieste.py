"""
Test unitari per la gestione richieste.
Copre src/pages/richieste.py.
"""

import datetime
import pandas as pd
import pytest
import streamlit as st
from pages.richieste import render_richieste_tab

def test_render_richieste_tab_materiali_success(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    
    mock_c1 = mocker.MagicMock()
    mock_c2 = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_c1, mock_c2])
    
    today = datetime.date.today()
    mock_c1.date_input.return_value = today
    mock_c2.date_input.return_value = today + datetime.timedelta(days=1)
    
    mocker.patch("streamlit.text_area", return_value="Materiali test")
    mocker.patch("streamlit.selectbox", return_value="Ferie")
    mocker.patch("streamlit.date_input", return_value=today)
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    mocker.patch("pages.richieste.add_material_request", return_value=True)
    mocker.patch("pages.richieste.salva_storico_materiali", return_value=True)
    mocker.patch("pages.richieste.get_material_requests", return_value=pd.DataFrame())
    
    render_richieste_tab("M1", "Tecnico", "User")
    assert mock_success.called

def test_render_richieste_tab_assenze_success(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)
    
    mock_c1 = mocker.MagicMock()
    mock_c2 = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_c1, mock_c2])
    
    today = datetime.date.today()
    mock_c1.date_input.return_value = today
    mock_c2.date_input.return_value = today + datetime.timedelta(days=1)
    
    mocker.patch("streamlit.date_input", return_value=today)
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    mocker.patch("pages.richieste.add_leave_request", return_value=True)
    mocker.patch("pages.richieste.salva_storico_assenze", return_value=True)
    mocker.patch("pages.richieste.get_leave_requests", return_value=pd.DataFrame())
    
    render_richieste_tab("M1", "Amministratore", "User")
    assert mock_success.called