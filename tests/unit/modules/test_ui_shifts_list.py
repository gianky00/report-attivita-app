"""
Test unitari per la visualizzazione della lista turni.
Copre src/pages/shifts/shifts_list_view.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.shifts.shifts_list_view import render_turni_list

def test_render_turni_list_empty(mocker):
    mock_info = mocker.patch("streamlit.info")
    render_turni_list(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "M1", "Tecnico", "test")
    assert mock_info.called

def test_render_turni_list_with_data(mocker):
    df_turni = pd.DataFrame([{
        "ID_Turno": "T1", "Descrizione": "Turno 1", "Data": "2025-01-01",
        "OrarioInizio": "08:00", "OrarioFine": "17:00",
        "PostiTecnico": 2, "PostiAiutante": 1
    }])
    df_bookings = pd.DataFrame(columns=["ID_Turno", "Matricola", "RuoloOccupato"])
    df_users = pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "User 1"}])
    
    mocker.patch("streamlit.checkbox", return_value=False)
    mocker.patch("streamlit.divider")
    mocker.patch("streamlit.container", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.caption")
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.selectbox", return_value="Tecnico")
    mock_button = mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.rerun")
    mocker.patch("streamlit.session_state", {})
    
    # Mocking logic
    mocker.patch("pages.shifts.shifts_list_view.prenota_turno_logic", return_value=True)

    render_turni_list(df_turni, df_bookings, df_users, "M1", "Tecnico", "test")
    assert mock_button.called

def test_render_turni_list_already_booked(mocker):
    df_turni = pd.DataFrame([{
        "ID_Turno": "T1", "Descrizione": "Turno 1", "Data": "2025-01-01",
        "OrarioInizio": "08:00", "OrarioFine": "17:00",
        "PostiTecnico": 2, "PostiAiutante": 1
    }])
    df_bookings = pd.DataFrame([{"ID_Turno": "T1", "Matricola": "M1", "RuoloOccupato": "Tecnico"}])
    df_users = pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "User 1"}])
    
    mocker.patch("streamlit.checkbox", return_value=False)
    mocker.patch("streamlit.divider")
    mocker.patch("streamlit.container", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.caption")
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock() for _ in range(3)])
    mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.rerun")
    mocker.patch("streamlit.session_state", {})
    
    # Mocking logic
    mocker.patch("pages.shifts.shifts_list_view.cancella_prenotazione_logic", return_value=True)

    render_turni_list(df_turni, df_bookings, df_users, "M1", "Tecnico", "test")
    assert mock_success.called
