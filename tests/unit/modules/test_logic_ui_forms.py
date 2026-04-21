"""
Test per la validazione e logica dei form utente.
"""

import datetime
import streamlit as st
from components.forms.debriefing_form import handle_submit
from components.forms.relazione_oncall_form import _handle_submission
from tests.unit.modules.st_mock_helper import MockSessionState

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
    mocker.patch("streamlit.session_state", MockSessionState({"debriefing_task": {}}))
    mocker.patch("components.forms.debriefing_form.scrivi_o_aggiorna_risposta", return_value=True)

    task = {"pdl": "123", "attivita": "Test", "section_key": "sec"}
    handle_submit("Report valido", "TERMINATA", task, "123", "2025-01-01")

    assert st.success.called
    assert "debriefing_task" not in st.session_state

def test_relazione_submission_validation(mocker):
    """Verifica la validazione dei campi obbligatori nella relazione."""
    mocker.patch("streamlit.error")
    mock_db = mocker.patch("components.forms.relazione_oncall_form.salva_relazione")

    # Firma: (dt, text, user, partner, t_start, t_end, pdl)
    # Data mancante o testo vuoto
    _handle_submission(None, "", "User", "Partner", "08:00", "16:00", "PDL1")

    assert st.error.called
    assert not mock_db.called

def test_relazione_submission_full_flow(mocker):
    """Verifica il flusso completo di invio relazione (DB + Email)."""
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")
    mocker.patch("streamlit.session_state", MockSessionState({"relazione_testo": "old"}))
    
    mock_db = mocker.patch(
        "components.forms.relazione_oncall_form.salva_relazione", return_value=True
    )
    # Il modulo relazione_oncall_form importa invia_email_con_outlook_async da email_sender
    mock_email = mocker.patch(
        "components.forms.relazione_oncall_form.invia_email_con_outlook_async"
    )

    dt = datetime.date(2025, 1, 1)
    _handle_submission(dt, "Testo relazione", "Tecnico Test", "Partner", "08:00", "16:00", "123456")

    assert mock_db.called
    assert mock_email.called
    assert st.session_state.relazione_testo == ""
