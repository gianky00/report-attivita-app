"""
Script di utility per l'aggiunta manuale di un utente amministratore.
"""

import sqlite3
import sys
from pathlib import Path

import bcrypt

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent))
from src.core.logging import get_logger

logger = get_logger(__name__)

DB_NAME = Path(__file__).parent.parent / "schedario.db"


def add_admin_user(matricola: str = "admin", nome: str = "Admin User"):
    """Crea un utente con privilegi di Amministratore nel database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Password di default (l'utente dovrà cambiarla)
        password = "admin_password"
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        cursor.execute(
            """
            INSERT INTO contatti (Matricola, "Nome Cognome", Ruolo, PasswordHash)
            VALUES (?, ?, ?, ?)
        """,
            (matricola, nome, "Amministratore", hashed_password.decode("utf-8")),
        )

        conn.commit()
        logger.info(
            f"Utente Amministratore '{nome}' (Matricola: {matricola}) creato."
        )

    except sqlite3.IntegrityError:
        logger.error(f"Errore: L'utente con matricola '{matricola}' esiste già.")
    except sqlite3.Error as e:
        logger.error(f"Errore durante l'aggiunta dell'amministratore: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    add_admin_user()
