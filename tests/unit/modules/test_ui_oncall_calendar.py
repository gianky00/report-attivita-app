"""
Test unitari per il calendario reperibilità.
Copre src/pages/shifts/oncall_calendar_view.py.
"""

import datetime
import pandas as pd
import pytest
import streamlit as st
from pages.shifts.oncall_calendar_view import render_reperibilita_tab

class MockSessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)

def test_render_reperibilita_tab_success(mocker):
    df_p = pd.DataFrame([{"ID_Turno": "T1", "Matricola": "M1", "RuoloOccupato": "Tecnico"}])
    df_u = pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "User 1"}])
    
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.divider")
    
    # Smart mock for columns
    mock_cols = [mocker.MagicMock() for _ in range(10)]
    mocker.patch("streamlit.columns", return_value=mock_cols)
    
    # Mock inner selectbox/buttons
    mock_cols[0].selectbox.return_value = 2025
    mock_cols[1].selectbox.return_value = "Gennaio"
    mock_cols[2].button.return_value = False
    
    mocker.patch("streamlit.button", return_value=False)
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.session_state", MockSessionState({"week_start_date": datetime.date.today()}))
    
    mocker.patch("pages.shifts.oncall_calendar_view.get_shifts_by_type", return_value=pd.DataFrame([{
        "ID_Turno": "T1", "Data": datetime.date.today().isoformat(), "Tipo": "Reperibilità"
    }]))
    mocker.patch("pages.shifts.oncall_calendar_view.get_shift_by_id", return_value={"Data": "2025-01-01"})
    
    render_reperibilita_tab(df_p, df_u, "M1", "Tecnico")
    assert st.subheader.called

def test_render_reperibilita_tab_admin_edit(mocker):
    session_state = MockSessionState({"editing_oncall_shift_id": "T1"})
    mocker.patch("streamlit.session_state", session_state)
    
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.container", return_value=mocker.MagicMock())
    
    # Mocking st.columns to return 2 mocks for the form
    mock_c1 = mocker.MagicMock()
    mock_c2 = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_c1, mock_c2])
    
    # Mocking buttons inside the form
    # The code does: c1, c2 = st.columns(2); if c1.button("Salva")... if c2.button("Annulla")...
    mock_c1.button.return_value = False
    mock_c2.button.return_value = True # Click Annulla
    
    mocker.patch("streamlit.rerun")
    mocker.patch("pages.shifts.oncall_calendar_view.get_shift_by_id", return_value={"Data": "2025-01-01", "ID_Turno": "T1"})
    mocker.patch("pages.shifts.oncall_calendar_view.get_all_users", return_value=pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "U1"}]))
    
    # Catch any rerun exception
    try:
        render_reperibilita_tab(pd.DataFrame(), pd.DataFrame(), "admin", "Amministratore")
    except BaseException:
        pass
        
    assert "editing_oncall_shift_id" not in session_state
