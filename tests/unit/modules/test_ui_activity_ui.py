"""
Test unitari per i componenti UI delle attività.
Copre src/components/ui/activity_ui.py.
"""

import pandas as pd
import pytest
import streamlit as st
from components.ui.activity_ui import disegna_sezione_attivita, visualizza_storico_organizzato

def test_visualizza_storico_organizzato(mocker):
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.toggle", return_value=True)
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.info")
    
    storico = [{"Data_Riferimento_dt": "2025-01-01", "Tecnico": "T1", "Report": "R1"}]
    visualizza_storico_organizzato(storico, "P1")
    assert st.markdown.called

def test_disegna_sezione_attivita_empty(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.session_state", {})
    
    disegna_sezione_attivita([], "test", "Tecnico")
    assert st.success.called

def test_disegna_sezione_attivita_with_data(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.button", return_value=False)
    mocker.patch("streamlit.session_state", {})
    mocker.patch("components.ui.activity_ui.get_unvalidated_reports_by_technician", return_value=pd.DataFrame())
    
    attivita = [{"pdl": "P1", "attivita": "A1", "data_attivita": pd.Timestamp("2025-01-01")}]
    disegna_sezione_attivita(attivita, "test", "Tecnico")
    assert st.header.called
