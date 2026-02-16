import sqlite3
from pathlib import Path

import bcrypt

DB_NAME = "schedario.db"


def reset_admin():
    if not Path(DB_NAME).exists():
        print(f"Errore: Database {DB_NAME} non trovato.")
        return

    new_password = "admin123"
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Cerchiamo l'admin (solitamente matricola 'admin' o ruolo 'Amministratore')
    cursor.execute("SELECT Matricola FROM contatti WHERE Ruolo = 'Amministratore' LIMIT 1")
    row = cursor.fetchone()

    if row:
        matricola = row[0]
        cursor.execute(
            "UPDATE contatti SET PasswordHash = ? WHERE Matricola = ?", (hashed, matricola)
        )
        conn.commit()
        print(f"Password per l'utente admin '{matricola}' resettata con successo a: {new_password}")
    else:
        print("Nessun utente con ruolo 'Amministratore' trovato. Lo creo...")
        # Uso le virgolette triple o escape per gestire gli spazi nei nomi colonna
        cursor.execute(
            'INSERT INTO contatti (Matricola, "Nome Cognome", Ruolo, PasswordHash) VALUES (?, ?, ?, ?)',
            ("admin", "Amministratore Sistema", "Amministratore", hashed),
        )
        conn.commit()
        print(f"Utente 'admin' creato con password: {new_password}")

    conn.close()


if __name__ == "__main__":
    reset_admin()
