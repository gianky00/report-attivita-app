"""
Test unitari per la gestione turni (router).
Copre src/pages/gestione_turni.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.gestione_turni import render_gestione_turni_tab

def test_render_gestione_turni_tab(mocker):
    mock_sub = mocker.patch("streamlit.subheader")
    # Mock nested tabs
    mocker.patch("streamlit.tabs", side_effect=[
        [mocker.MagicMock() for _ in range(3)], # Outer tabs
        [mocker.MagicMock() for _ in range(3)]  # Inner tabs
    ])
    
    mocker.patch("pages.gestione_turni.get_all_bookings", return_value=pd.DataFrame())
    mocker.patch("pages.gestione_turni.get_all_users", return_value=pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "T1"}]))
    mocker.patch("pages.gestione_turni.get_all_bacheca_items", return_value=pd.DataFrame())
    mocker.patch("pages.gestione_turni.get_all_substitutions", return_value=pd.DataFrame())
    mocker.patch("pages.gestione_turni.get_shifts_by_type", return_value=pd.DataFrame())
    
    # Mocking sub-renders
    mocker.patch("pages.gestione_turni.render_turni_list")
    mocker.patch("pages.gestione_turni.render_reperibilita_tab")
    mocker.patch("pages.gestione_turni.render_bacheca_tab")
    mocker.patch("pages.gestione_turni.render_sostituzioni_tab")

    render_gestione_turni_tab("M1", "Tecnico")
    assert mock_sub.called
