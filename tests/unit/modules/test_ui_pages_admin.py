"""
Test unitari per le pagine amministrative (IA e Log).
Copre src/pages/admin/ia_view.py e src/pages/admin/logs_view.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.admin.ia_view import render_ia_management_tab
from pages.admin.logs_view import render_access_logs_tab

def test_render_ia_management_tab(mocker):
    mock_sub = mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("pages.admin.ia_view.learning_module.load_unreviewed_knowledge", return_value=[
        {"id": "E1", "stato": "in attesa di revisione", "attivita_collegata": "A", "data_suggerimento": "2025-01-01T10:00:00", "suggerito_da": "T1", "pdl": "P1", "dettagli_report": {}}
    ])
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.text_input", return_value="key")
    mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("pages.admin.ia_view.learning_module.integrate_knowledge", return_value={"success": True})
    mocker.patch("streamlit.rerun")
    
    render_ia_management_tab()
    assert mock_sub.called

def test_render_access_logs_tab_empty(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_warn = mocker.patch("streamlit.warning")
    mocker.patch("pages.admin.logs_view.get_access_logs", return_value=pd.DataFrame())
    
    render_access_logs_tab()
    assert mock_warn.called

def test_render_access_logs_tab_with_data(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.multiselect", return_value=[])
    mocker.patch("streamlit.date_input", return_value=None)
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("streamlit.divider")
    mock_df_st = mocker.patch("streamlit.dataframe")
    
    df = pd.DataFrame([{"timestamp": "2025-01-01 10:00:00", "username": "admin", "status": "success"}])
    mocker.patch("pages.admin.logs_view.get_access_logs", return_value=df)
    
    render_access_logs_tab()
    assert mock_df_st.called
