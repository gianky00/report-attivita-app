"""
Test di sicurezza per il modulo di autenticazione.
Focalizzato sulla prevenzione della Privilege Escalation e bootstrapping sicuro.
"""

import pytest
from src.modules.auth import authenticate_user

def test_first_user_is_always_admin(mocker):
    """Verifica che se il DB è vuoto, il primo utente riceva il ruolo Amministratore."""
    # Mock di una connessione che restituisce 0 utenti
    mock_conn = mocker.MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = [0] # Count = 0
    
    mocker.patch("src.modules.auth.get_db_connection", return_value=mock_conn)
    
    # Tentativo di login con qualsiasi credenziale su DB vuoto
    status, data = authenticate_user("99999", "nuova_password")
    
    assert status == "FIRST_LOGIN_SETUP"
    # data[1] è il ruolo assegnato
    assert data[1] == "Amministratore"
    assert "Admin User" in data[0]

def test_authenticate_user_not_found_returns_failed(mocker):
    """Verifica che un utente non esistente non possa bypassare i controlli."""
    mock_conn = mocker.MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = [5] # Ci sono già altri utenti
    
    mocker.patch("src.modules.auth.get_db_connection", return_value=mock_conn)
    mocker.patch("src.modules.auth.get_user_by_matricola", return_value=None)
    
    status, _ = authenticate_user("NON_EXIST", "any")
    assert status == "FAILED"
