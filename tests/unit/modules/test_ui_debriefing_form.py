import pytest
import streamlit as st
from components.forms.debriefing_form import handle_submit, render_debriefing_ui

class MockSessionState(dict):
    def __getattr__(self, item):
        if item in self:
            return self[item]
        raise AttributeError(item)
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, item):
        if item in self:
            del self[item]
        else:
            raise AttributeError(item)

def test_handle_submit(mocker):
    session = MockSessionState()
    mocker.patch("streamlit.session_state", session)
    mocker.patch("streamlit.success")
    mocker.patch("streamlit.balloons")
    mocker.patch("components.forms.debriefing_form.scrivi_o_aggiorna_risposta", return_value=True)
    
    task = {"pdl": "P1", "attivita": "A1", "section_key": "today"}
    session["debriefing_task"] = task
    
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
    mocker.patch("streamlit.markdown")
    
    render_debriefing_ui({}, "M1", "2025-01-01")
    assert st.subheader.called
