"""
Test per la sicurezza e resilienza delle sessioni.
"""

import json
from modules.session_manager import load_session

def test_load_session_with_missing_keys(tmp_path, mocker, monkeypatch):
    """Verifica che una sessione con JSON incompleto venga invalidata."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sessions").mkdir()

    token = "incomplete-token"
    session_file = tmp_path / "sessions" / f"session_{token}.json"
    session_file.write_text(json.dumps({"ruolo": "Tecnico"}), encoding="utf-8")

    mocker.patch("src.modules.session_manager.SESSION_DIR", tmp_path / "sessions")    

    # La funzione deve restituire False se mancano chiavi critiche come authenticated_user
    assert load_session(token) is False

def test_load_session_with_wrong_data_types(tmp_path, mocker, monkeypatch):
    """Verifica la gestione di tipi dati errati nel JSON di sessione."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sessions").mkdir()

    token = "wrong-type-token"
    session_file = tmp_path / "sessions" / f"session_{token}.json"
    session_file.write_text(json.dumps({
        "authenticated_user": 12345, # Dovrebbe essere str
        "ruolo": "Tecnico"
    }), encoding="utf-8")

    mocker.patch("src.modules.session_manager.SESSION_DIR", tmp_path / "sessions")    

    assert load_session(token) is False