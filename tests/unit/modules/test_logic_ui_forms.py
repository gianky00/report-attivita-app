"""
Test per la validazione e logica dei form utente.
"""

import pytest
import streamlit as st
import datetime
from components.forms.debriefing_form import handle_submit
from components.forms.relazione_oncall_form import _handle_submission

def test_debriefing_form_validation(mocker):
    """Verifica che il report non possa essere vuoto."""
    mocker.patch("streamlit.warning")
    mock_save = mocker.patch("components.forms.debriefing_form.scrivi_o_aggiorna_risposta")
    
    task = {"pdl": "123", "attivita": "Test", "section_key": "sec"}
    
    # Esecuzione con testo vuoto
    handle_submit("   ", "TERMINATA", task, "123", "2025-01-01")
    
    assert st.warning.called
    assert not mock_save.called

def test_debriefing_form_success(mocker):
    """Verifica il comportamento in caso di successo del salvataggio."""
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.balloons")
    mocker.patch("components.forms.debriefing_form.scrivi_o_aggiorna_risposta", return_value=True)
    
    task = {"pdl": "123", "attivita": "Test", "section_key": "sec"}
    st.session_state.debriefing_task = task
    
    handle_submit("Report valido", "TERMINATA", task, "123", "2025-01-01")
    
    assert st.success.called
    assert "debriefing_task" not in st.session_state

def test_relazione_submission_validation(mocker):
    """Verifica la validazione dei campi obbligatori nella relazione."""
    mocker.patch("streamlit.error")
    mock_db = mocker.patch("components.forms.relazione_oncall_form.salva_relazione")
    
    # Data mancante o testo vuoto
    _handle_submission(None, "", "User", "Partner", "08:00", "16:00")
    
    assert st.error.called
    assert not mock_db.called

def test_relazione_submission_full_flow(mocker):
    """Verifica il flusso completo di invio relazione (DB + Email)."""
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    mock_db = mocker.patch("components.forms.relazione_oncall_form.salva_relazione", return_value=True)
    mock_email = mocker.patch("components.forms.relazione_oncall_form.invia_email_con_outlook_async")
    
    dt = datetime.date(2025, 1, 1)
    _handle_submission(dt, "Testo relazione", "Tecnico", "Partner", "08:00", "16:00")
    
    assert mock_db.called
    assert mock_email.called
    assert st.session_state.relazione_testo == ""
