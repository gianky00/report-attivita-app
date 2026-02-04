"""
Test unitari per la gestione delle sessioni utente.
"""

import src.modules.session_manager as sm
from src.modules.session_manager import delete_session, load_session, save_session


def test_save_and_load_session(tmp_path, monkeypatch, mocker):
    """Verifica il salvataggio e il caricamento corretto di una sessione."""
    # Mock della directory delle sessioni
    test_session_dir = tmp_path / "sessions"
    test_session_dir.mkdir()
    monkeypatch.setattr(sm, "SESSION_DIR", test_session_dir)

    # Mock di streamlit session_state
    mock_st = mocker.patch("src.modules.session_manager.st")
    mock_st.session_state = mocker.MagicMock()

    token = save_session("12345", "Tecnico")
    assert token is not None

    # Verifica esistenza file
    session_file = test_session_dir / f"session_{token}.json"
    assert session_file.exists()

    # Caricamento
    success = load_session(token)
    assert success is True
    assert mock_st.session_state.authenticated_user == "12345"
    assert mock_st.session_state.ruolo == "Tecnico"


def test_load_invalid_token(tmp_path, monkeypatch):
    """Verifica che un token non valido restituisca False."""
    assert load_session("invalid-token") is False
    assert load_session("") is False


def test_delete_session(tmp_path, monkeypatch):
    """Verifica la cancellazione di una sessione."""
    test_session_dir = tmp_path / "sessions"
    test_session_dir.mkdir()
    monkeypatch.setattr(sm, "SESSION_DIR", test_session_dir)

    # Crea un file finto
    token = "test-token"
    session_file = test_session_dir / f"session_{token}.json"
    session_file.write_text("{}", encoding="utf-8")

    delete_session(token)
    assert not session_file.exists()
