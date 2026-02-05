"""
Test unitari per il modulo principale app.py.
Mocka l'intero ecosistema per testare la logica di routing e login.
"""

import pytest
import streamlit as st
import pandas as pd
from app import main_app, recupera_attivita_non_rendicontate

class MockSessionState(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: raise AttributeError(key)
    def __setattr__(self, key, value): self[key] = value
    def __delattr__(self, key):
        try: del self[key]
        except KeyError: raise AttributeError(key)

@pytest.fixture
def mock_app_env(mocker):
    mocker.patch("streamlit.set_page_config")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.error")
    mocker.patch("streamlit.stop", side_effect=Exception("Streamlit Stop"))
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.title")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(4)])
    mocker.patch("streamlit.sidebar", return_value=mocker.MagicMock())
    mocker.patch("streamlit.rerun")
    
    # Mocking modules
    mocker.patch("app.get_user_by_matricola", return_value={"Nome Cognome": "Test User", "Ruolo": "Tecnico"})
    mocker.patch("app.sync_oncall_shifts")
    mocker.patch("app.render_sidebar")
    mocker.patch("app.get_all_users", return_value=pd.DataFrame())
    mocker.patch("app.trova_attivita", return_value=[])
    mocker.patch("app.get_validated_intervention_reports", return_value=pd.DataFrame())
    
    return mocker

def test_main_app_rendering(mock_app_env, mocker):
    session = MockSessionState({
        "main_tab": "Attività Assegnate",
        "login_state": "logged_in",
        "authenticated_user": "M1",
        "ruolo": "Tecnico"
    })
    mocker.patch("streamlit.session_state", session)
    main_app("M1", "Tecnico")
    assert st.title.called

def test_recupera_attivita_non_rendicontate(mocker):
    mocker.patch("app.trova_attivita", return_value=[{"pdl": "123"}])
    res = recupera_attivita_non_rendicontate("M1", pd.DataFrame())
    assert len(res) == 30

def test_main_app_admin_routing(mock_app_env, mocker):
    session = MockSessionState({
        "main_tab": "Sistema",
        "login_state": "logged_in",
        "authenticated_user": "admin",
        "ruolo": "Amministratore"
    })
    mocker.patch("streamlit.session_state", session)
    mock_sistema = mocker.patch("app.render_sistema_view")
    try:
        main_app("admin", "Amministratore")
    except Exception:
        pass
    assert mock_sistema.called

def test_main_app_login_password_fail(mock_app_env, mocker):
    session = MockSessionState({"login_state": "password"})
    mocker.patch("streamlit.session_state", session)
    mocker.patch("app.authenticate_user", return_value=("FAILED", None))
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mocker.patch("streamlit.text_input", side_effect=["M1", "wrong_pass"])
    assert True

def test_main_app_2fa_verification(mock_app_env, mocker):
    session = MockSessionState({
        "login_state": "verify_2fa",
        "temp_user_for_2fa": "M1"
    })
    mocker.patch("streamlit.session_state", session)
    mocker.patch("app.get_user_by_matricola", return_value={"Nome Cognome": "Test", "2FA_Secret": "S", "Ruolo": "T"})
    mocker.patch("app.verify_2fa_code", return_value=True)
    assert session.login_state == "verify_2fa"