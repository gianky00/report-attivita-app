"""
Test unitari per la bacheca e sostituzioni.
Copre src/pages/shifts/market_view.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.shifts.market_view import render_bacheca_tab, render_sostituzioni_tab

def test_render_bacheca_tab_success(mocker):
    df_b = pd.DataFrame([{
        "ID_Bacheca": "B1", "ID_Turno": "T1", "Stato": "Disponibile", 
        "Ruolo_Originale": "Tecnico", "Timestamp_Pubblicazione": "2025-01-01"
    }])
    df_u = pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "User 1"}])
    m_to_n = {"M1": "User 1"}
    
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.container", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.caption")
    mock_button = mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.rerun")
    
    mocker.patch("pages.shifts.market_view.get_shift_by_id", return_value={
        "Descrizione": "Desc", "Data": "2025-01-01", "OrarioInizio": "08:00", "OrarioFine": "17:00"
    })
    mocker.patch("pages.shifts.market_view.prendi_turno_da_bacheca_logic", return_value=True)

    render_bacheca_tab(df_b, df_u, "M1", "Tecnico", m_to_n)
    assert mock_button.called

def test_render_sostituzioni_tab(mocker):
    df_s = pd.DataFrame([{
        "ID_Richiesta": "S1", "Ricevente_Matricola": "M1", 
        "Richiedente_Matricola": "M2", "ID_Turno": "T1"
    }])
    m_to_n = {"M1": "User 1", "M2": "User 2"}
    
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.container", return_value=mocker.MagicMock())
    mocker.patch("streamlit.write")
    mock_button = mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.rerun")
    
    mocker.patch("pages.shifts.market_view.rispondi_sostituzione_logic", return_value=True)

    render_sostituzioni_tab(df_s, m_to_n, "M1")
    assert mock_button.called
