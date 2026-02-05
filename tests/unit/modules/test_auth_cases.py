"""
Test unitari avanzati per il modulo di autenticazione.
Copre casi limite come password errate, 2FA malformati e setup amministratore.
"""

import bcrypt
import pytest
from modules.auth import (
    authenticate_user,
    create_user,
    verify_2fa_code,
)

@pytest.fixture
def mock_auth_db(mocker):
    """Fixture per mockare la connessione al database in auth.py."""
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mocker.patch("src.modules.auth.get_db_connection", return_value=mock_conn)
    return mock_conn

def test_authenticate_user_wrong_password(mocker, mock_auth_db):
    """Verifica che l'autenticazione fallisca con una password non corrispondente."""
    mock_cursor = mock_auth_db.cursor.return_value
    # Simula che ci siano utenti nel sistema
    mock_cursor.fetchone.return_value = [10] 
    
    mock_user = {
        "Matricola": "12345",
        "Nome Cognome": "Test User",
        "Ruolo": "Tecnico",
        "PasswordHash": bcrypt.hashpw(b"correct_pass", bcrypt.gensalt()).decode("utf-8"),
        "2FA_Secret": "JBSWY3DPEHPK3PXP"
    }
    mocker.patch("src.modules.auth.get_user_by_matricola", return_value=mock_user)
    
    # Password errata
    status, _ = authenticate_user("12345", "wrong_pass")
    assert status == "FAILED"

def test_verify_2fa_code_malformed_secret():
    """Verifica che un segreto 2FA non valido non causi crash e restituisca False."""
    assert verify_2fa_code("invalid-secret-@#$!", "123456") is False

def test_create_first_admin_setup(mocker, mock_auth_db):
    """Verifica la logica di creazione di un nuovo utente (primo setup)."""
    # create_user usa conn.execute direttamente
    user_data = {
        "Matricola": "ADMIN01",
        "Nome Cognome": "Amministratore Sistema",
        "Ruolo": "Amministratore",
        "PasswordHash": "hash_fittizio"
    }
    
    success = create_user(user_data)
    assert success is True
    assert mock_auth_db.execute.called
    
    # Verifica che la query SQL contenga le colonne corrette
    args = mock_auth_db.execute.call_args[0]
    assert "INSERT INTO contatti" in args[0]
    assert "ADMIN01" in args[1][0] # Matricola è il primo parametro nella lista valori
