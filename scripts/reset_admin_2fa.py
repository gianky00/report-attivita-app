"""
Script di emergenza per resettare il segreto 2FA di un utente.
"""

import sqlite3
import sys
from pathlib import Path

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent / "src"))
from core.logging import get_logger

logger = get_logger(__name__)

DB_NAME = Path(__file__).parent.parent / "schedario.db"


def reset_user_2fa(matricola: str):
    """Rimuove il segreto 2FA per l'utente specificato nel database."""
    conn = None
    try:
        if not DB_NAME.exists():
            logger.error(f"Database non trovato: {DB_NAME}")
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE contatti SET "2FA_Secret" = NULL WHERE Matricola = ?', (matricola,)
        )

        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"2FA per '{matricola}' resettata con successo.")
            logger.info("L'utente dovrà riconfigurare la sicurezza.")
        else:
            logger.warning(f"Matricola '{matricola}' non trovata.")

    except sqlite3.Error as e:
        logger.error(f"Errore database: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/reset_admin_2fa.py <Matricola>")
        sys.exit(1)

    reset_user_2fa(sys.argv[1])
