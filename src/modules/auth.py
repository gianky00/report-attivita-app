"""
Modulo per la gestione dell'autenticazione e degli utenti.
Include funzioni per la gestione del database utenti e la sicurezza 2FA.
"""

import datetime
import sqlite3
from typing import Any

import bcrypt
import pyotp

from constants import VALID_USER_COLUMNS
from core.database import DatabaseEngine
from core.logging import get_logger

logger = get_logger(__name__)


def get_user_by_matricola(matricola: str) -> dict[str, Any] | None:
    """Recupera un utente dal database tramite la sua matricola."""
    conn = DatabaseEngine.get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM contatti WHERE Matricola = ?"
        cursor.execute(query, (matricola,))
        user_row = cursor.fetchone()
        return dict(user_row) if user_row else None
    except sqlite3.Error as e:
        logger.error(f"Errore nel recuperare l'utente {matricola}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def create_user(user_data: dict[str, Any]) -> bool:
    """Crea un nuovo utente nel database."""
    # Filtra solo le chiavi valide
    filtered_data = {k: v for k, v in user_data.items() if k in VALID_USER_COLUMNS}

    # Auto-populate "Nome Cognome" if missing but separate fields exist
    if (
        "Nome" in filtered_data
        and "Cognome" in filtered_data
        and "Nome Cognome" not in filtered_data
    ):
        filtered_data["Nome Cognome"] = f"{filtered_data['Nome']} {filtered_data['Cognome']}"

    if not filtered_data:
        return False

    conn = DatabaseEngine.get_connection()
    try:
        with conn:
            cols = ", ".join(f'"{k}"' for k in filtered_data)
            placeholders = ", ".join("?" for _ in filtered_data)
            sql = f"INSERT INTO contatti ({cols}) VALUES ({placeholders})"  # nosec B608
            conn.execute(sql, list(filtered_data.values()))
        return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        logger.error(f"Errore durante la creazione dell'utente: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_user(matricola: str, update_data: dict[str, Any]) -> bool:
    """Aggiorna i dati di un utente esistente."""
    # Filtra solo le chiavi valide
    filtered_data = {k: v for k, v in update_data.items() if k in VALID_USER_COLUMNS}
    if not filtered_data:
        return False

    conn = DatabaseEngine.get_connection()
    try:
        with conn:
            set_clause = ", ".join(f'"{k}" = ?' for k in filtered_data)
            sql = f"UPDATE contatti SET {set_clause} WHERE Matricola = ?"  # nosec B608
            params = [*list(filtered_data.values()), matricola]
            conn.execute(sql, params)
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore durante l'aggiornamento dell'utente {matricola}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def delete_user(matricola: str) -> bool:
    """Cancella un utente dal database."""
    conn = DatabaseEngine.get_connection()
    try:
        with conn:
            sql = "DELETE FROM contatti WHERE Matricola = ?"
            conn.execute(sql, (matricola,))
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore durante l'eliminazione dell'utente {matricola}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def reset_user_password(matricola: str) -> bool:
    """Resetta la password di un utente impostando PasswordHash a NULL."""
    return update_user(matricola, {"PasswordHash": None})


def reset_user_2fa(matricola: str) -> bool:
    """Resetta il 2FA di un utente impostando 2FA_Secret a NULL."""
    return update_user(matricola, {"2FA_Secret": None})


def change_user_password(matricola: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Cambia la password dell'utente verificando la vecchia."""
    user = get_user_by_matricola(matricola)
    if not user:
        return False, "Utente non trovato."

    password_hash = user.get("PasswordHash")
    if not password_hash:
        return False, "Password non impostata. Contatta l'amministratore."

    try:
        if not bcrypt.checkpw(old_password.encode("utf-8"), str(password_hash).encode("utf-8")):
            return False, "La vecchia password non è corretta."

        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        if update_user(matricola, {"PasswordHash": new_hash}):
            return True, "Password aggiornata con successo."
        return False, "Errore durante l'aggiornamento del database."
    except Exception as e:
        logger.error(f"Errore cambio password per {matricola}: {e}")
        return False, f"Errore interno: {e}"


def generate_2fa_secret() -> str:
    """Genera una nuova chiave segreta per la 2FA."""
    return pyotp.random_base32()


def get_provisioning_uri(username: str, secret: str) -> str:
    """Genera l'URI di provisioning per il QR code."""
    safe_username = "".join(c for c in username if c.isalnum())
    return str(
        pyotp.totp.TOTP(secret).provisioning_uri(
            name=safe_username, issuer_name="AppManutenzioneSMI"
        )
    )


def verify_2fa_code(secret: str, code: str) -> bool:
    """Verifica un codice 2FA fornito dall'utente."""
    if not secret or not code:
        return False
    try:
        totp = pyotp.totp.TOTP(secret)
        return totp.verify(code)
    except Exception:
        return False


def authenticate_user(matricola: str, password: str) -> tuple[str, Any]:
    """Autentica un utente tramite Matricola e gestisce il flusso 2FA."""
    if not matricola or not password:
        return "FAILED", None

    conn = DatabaseEngine.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM contatti")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            # Primo utente in assoluto come Amministratore.
            nome_completo = f"Admin User ({matricola})"
            return "FIRST_LOGIN_SETUP", (nome_completo, "Amministratore", password)

        user_row = get_user_by_matricola(matricola)
        if not user_row:
            return "FAILED", None

        # Controllo stato account
        if user_row.get("Stato") == "Disabilitato":
            return "DISABLED", None

        nome_completo = str(user_row["Nome Cognome"]).strip()
        ruolo = user_row.get("Ruolo", "Tecnico")
        password_bytes = password.encode("utf-8")

        password_hash = user_row.get("PasswordHash")
        if not password_hash or not str(password_hash).strip():
            return "FIRST_LOGIN_SETUP", (nome_completo, ruolo, password)

        try:
            hashed_password_bytes = str(password_hash).encode("utf-8")
            if bcrypt.checkpw(password_bytes, hashed_password_bytes):
                # Se l'utente ha la 2FA configurata, la richiediamo
                if user_row.get("2FA_Secret"):
                    return "2FA_REQUIRED", nome_completo
                # Altrimenti, l'accesso è diretto (2FA facoltativa e non attiva)
                return "SUCCESS", (nome_completo, ruolo)
            return "FAILED", None
        except (ValueError, TypeError):
            return "FIRST_LOGIN_SETUP", (nome_completo, ruolo, password)
    finally:
        if conn:
            conn.close()


def log_access_attempt(username: str, status: str) -> bool:
    """Registra un tentativo di accesso direttamente nel database."""
    conn = DatabaseEngine.get_connection()
    try:
        with conn:
            sql = "INSERT INTO access_logs (timestamp, username, status) VALUES (?, ?, ?)"
            now_iso = datetime.datetime.now().isoformat()
            conn.execute(sql, (now_iso, username, status))
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore registrazione tentativo accesso: {e}")
        return False
    finally:
        if conn:
            conn.close()
