"""
Test unitari per il router amministrativo.
Copre src/pages/admin/__init__.py.
"""

import pytest
import streamlit as st

def test_render_caposquadra_view(mocker):
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    
    # Mocking lazy imports
    mocker.patch("pages.admin.shifts_view.render_new_shift_form")
    mocker.patch("pages.admin.validation_view.render_report_validation_tab")
    mocker.patch("pages.admin.validation_view.render_relazioni_validation_tab")
    
    from pages.admin import render_caposquadra_view
    render_caposquadra_view("M1")
    assert st.tabs.called

def test_render_sistema_view(mocker):
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(4)])
    
    # Mocking lazy imports
    mocker.patch("pages.admin.ia_view.render_ia_management_tab")
    mocker.patch("pages.admin.logs_view.render_access_logs_tab")
    mocker.patch("pages.admin.users_view.render_gestione_account")
    mocker.patch("pages.gestione_dati.render_gestione_dati_tab")
    
    from pages.admin import render_sistema_view
    render_sistema_view()
    assert st.tabs.called
