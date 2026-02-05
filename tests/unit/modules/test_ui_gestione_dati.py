"""
Test unitari per la gestione dati e esclusioni.
Copre src/pages/gestione_dati.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.gestione_dati import render_gestione_dati_tab

def test_render_gestione_dati_tab_success(mocker):
    # Patching Streamlit
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.error")
    mocker.patch("streamlit.warning")
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.divider")
    mocker.patch("streamlit.selectbox", side_effect=lambda label, options, **kwargs: options[1] if options and len(options)>1 else (options[0] if options else None))
    mocker.patch("streamlit.data_editor", side_effect=lambda df, **kwargs: df)
    mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.rerun")
    mocker.patch("streamlit.session_state", {"authenticated_user": "M1"})

    # Patching module imports within gestione_dati
    mocker.patch("pages.gestione_dati.get_table_names", return_value=["table1", "table2"])
    mocker.patch("pages.gestione_dati.get_table_data", return_value=pd.DataFrame([{"id": 1}]))
    mocker.patch("pages.gestione_dati.save_table_data", return_value=True)
    mocker.patch("pages.gestione_dati.get_all_users", return_value=pd.DataFrame([{"Matricola": "M1", "Nome Cognome": "T1", "Ruolo": "Tecnico"}]))
    mocker.patch("pages.gestione_dati.get_all_assigned_activities", return_value=[])
    mocker.patch("pages.gestione_dati.get_validated_intervention_reports", return_value=pd.DataFrame())

    render_gestione_dati_tab()
    assert mock_success.called

def test_render_gestione_dati_tab_no_tables(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_warning = mocker.patch("streamlit.warning")
    mocker.patch("streamlit.session_state", {})
    
    mocker.patch("pages.gestione_dati.get_table_names", return_value=[])
    
    render_gestione_dati_tab()
    assert mock_warning.called