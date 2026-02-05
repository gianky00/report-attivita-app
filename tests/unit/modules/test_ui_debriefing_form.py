"""
Test unitari per il form di debriefing.
Copre src/components/forms/debriefing_form.py.
"""

import pytest
import streamlit as st
from components.forms.debriefing_form import render_debriefing_ui, handle_submit

class MockSessionState(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: raise AttributeError(key)
    def __setattr__(self, key, value): self[key] = value
    def __delattr__(self, key):
        try: del self[key]
        except KeyError: raise AttributeError(key)

def test_handle_submit_success(mocker):
    session = MockSessionState({})
    mocker.patch("streamlit.session_state", session)
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.balloons")
    mocker.patch("components.forms.debriefing_form.scrivi_o_aggiorna_risposta", return_value=True)
    
    task = {"pdl": "P1", "attivita": "A1", "section_key": "today"}
    session.debriefing_task = task
    
    assert handle_submit("Test report", "TERMINATA", task, "M1", "2025-01-01") is True
    assert "debriefing_task" not in session

def test_render_debriefing_ui(mocker):
    task = {"pdl": "P1", "attivita": "A1", "section_key": "today"}
    session = MockSessionState({"debriefing_task": task})
    mocker.patch("streamlit.session_state", session)
    mocker.patch("streamlit.title")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.text_area", return_value="Rep")
    mocker.patch("streamlit.selectbox", return_value="TERMINATA")
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock(), mocker.MagicMock()])
    mocker.patch("streamlit.button", return_value=False)
    
    render_debriefing_ui({}, "M1", "2025-01-01")
    assert st.title.called
