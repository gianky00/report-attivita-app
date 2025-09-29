import sqlite3
import os

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"

def crea_tabella():
    """
    Crea la tabella per le attività programmate in un database SQLite.
    La funzione è idempotente: non farà nulla se la tabella esiste già.
    """
    conn = None
    try:
        # Connettiti al database (verrà creato se non esiste)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Definisci la struttura della tabella.
        # Le colonne sono basate sul DataFrame generato in data_manager.py
        # Usiamo TEXT per la maggior parte delle colonne per flessibilità.
        # Il campo Storico verrà memorizzato come una stringa JSON.
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            PdL TEXT,
            Impianto TEXT,
            Descrizione TEXT,
            Stato_OdL TEXT,
            Lunedì TEXT,
            Martedì TEXT,
            Mercoledì TEXT,
            Giovedì TEXT,
            Venerdì TEXT,
            TCL TEXT,
            Area TEXT,
            GiorniProgrammati TEXT,
            Stato TEXT,
            Storico TEXT
        );
        """

        # Esegui la query
        cursor.execute(create_table_query)

        # Commit delle modifiche
        conn.commit()

        print(f"Database '{DB_NAME}' e tabella '{TABLE_NAME}' pronti per l'uso.")

    except sqlite3.Error as e:
        print(f"Errore durante la creazione del database: {e}")
    finally:
        # Chiudi la connessione
        if conn:
            conn.close()

if __name__ == "__main__":
    crea_tabella()