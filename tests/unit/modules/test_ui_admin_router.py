"""
Test unitari per il router amministrativo.
"""

import pytest
from unittest.mock import MagicMock

def test_render_caposquadra_view(mocker):
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(2)])
    
    # Mock lazy imports inside functions
    mocker.patch("pages.admin.validation_view.render_report_validation_tab")
    mocker.patch("pages.admin.validation_view.render_relazioni_validation_tab")
    
    from pages.admin import render_caposquadra_view
    # Richiede matricola_utente
    render_caposquadra_view("ADMIN01")
    assert True

def test_render_sistema_view(mocker):
    mocker.patch("streamlit.markdown")
    # Ora ci sono 6 tab: Gestione Account, Audit, Cronologia Accessi, Gestione Dati, Gestione IA, Stato Sistema
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(6)])

    # Mocking lazy imports inside render_sistema_view
    mocker.patch("pages.admin.users_view.render_gestione_account")
    mocker.patch("pages.admin.audit_view.render_audit_tab")
    mocker.patch("pages.admin.logs_view.render_access_logs_tab")
    mocker.patch("pages.gestione_dati.render_gestione_dati_tab")
    mocker.patch("pages.admin.ia_view.render_ia_management_tab")
    mocker.patch("pages.admin.system_status_view.render_system_status_tab")

    from pages.admin import render_sistema_view
    render_sistema_view()
    assert True
