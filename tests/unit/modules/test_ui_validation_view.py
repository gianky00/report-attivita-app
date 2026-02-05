"""
Test unitari per la validazione dei report.
Copre src/pages/admin/validation_view.py.
"""

import pandas as pd
import pytest
import streamlit as st
from pages.admin.validation_view import render_report_validation_tab, render_relazioni_validation_tab

def test_render_report_validation_tab_empty(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("pages.admin.validation_view.get_reports_to_validate", return_value=pd.DataFrame())
    
    render_report_validation_tab("M123")
    assert mock_success.called

def test_render_report_validation_tab_process(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.data_editor", side_effect=lambda df, **kwargs: df)
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock() for _ in range(3)])
    mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.spinner", return_value=mocker.MagicMock())
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    df = pd.DataFrame([{"id_report": "R1", "pdl": "P1", "testo_report": "T", "stato_attivita": "In corso"}])
    mocker.patch("pages.admin.validation_view.get_reports_to_validate", return_value=df)
    mocker.patch("pages.admin.validation_view.process_and_commit_validated_reports", return_value=True)
    
    render_report_validation_tab("M123")
    assert mock_success.called

def test_render_relazioni_validation_tab_success(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.data_editor", side_effect=lambda df, **kwargs: df)
    mocker.patch("streamlit.button", return_value=True)
    mocker.patch("streamlit.spinner", return_value=mocker.MagicMock())
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    
    df = pd.DataFrame([{"id_relazione": "REL1", "data_intervento": "2025-01-01"}])
    mocker.patch("pages.admin.validation_view.get_unvalidated_relazioni", return_value=df)
    mocker.patch("pages.admin.validation_view.process_and_commit_validated_relazioni", return_value=True)
    
    render_relazioni_validation_tab("M123")
    assert mock_success.called
