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

        # Definisci la struttura della tabella per le attività programmate
        cursor.execute(f"""
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
        """)

        # Definisci e crea le tabelle per i dati gestionali
        tabelle_gestionali = {
            "contatti": """(
                "Nome Cognome" TEXT PRIMARY KEY,
                Password TEXT,
                Ruolo TEXT,
                PasswordHash TEXT,
                "Link Attività" TEXT,
                "2FA_Secret" TEXT,
                Matricola TEXT
            )""",
            "turni": """(
                ID_Turno TEXT PRIMARY KEY,
                Descrizione TEXT,
                Data TEXT,
                OrarioInizio TEXT,
                OrarioFine TEXT,
                PostiTecnico INTEGER,
                PostiAiutante INTEGER,
                Tipo TEXT
            )""",
            "prenotazioni": """(
                ID_Prenotazione TEXT PRIMARY KEY,
                ID_Turno TEXT,
                "Nome Cognome" TEXT,
                RuoloOccupato TEXT,
                Timestamp TEXT
            )""",
            "sostituzioni": """(
                ID_Richiesta TEXT PRIMARY KEY,
                ID_Turno TEXT,
                Richiedente TEXT,
                Ricevente TEXT,
                Timestamp TEXT
            )""",
            "notifiche": """(
                ID_Notifica TEXT PRIMARY KEY,
                Timestamp TEXT,
                Destinatario TEXT,
                Messaggio TEXT,
                Stato TEXT,
                Link_Azione TEXT
            )""",
            "bacheca": """(
                ID_Bacheca TEXT PRIMARY KEY,
                ID_Turno TEXT,
                Tecnico_Originale TEXT,
                Ruolo_Originale TEXT,
                Timestamp_Pubblicazione TEXT,
                Stato TEXT,
                Tecnico_Subentrante TEXT,
                Timestamp_Assegnazione TEXT
            )""",
            "richieste_materiali": """(
                ID_Richiesta TEXT PRIMARY KEY,
                Richiedente TEXT,
                Timestamp TEXT,
                Stato TEXT,
                Dettagli TEXT
            )""",
            "richieste_assenze": """(
                ID_Richiesta TEXT PRIMARY KEY,
                Richiedente TEXT,
                Timestamp TEXT,
                Tipo_Assenza TEXT,
                Data_Inizio TEXT,
                Data_Fine TEXT,
                Note TEXT,
                Stato TEXT
            )""",
             "access_logs": """(
                timestamp TEXT,
                username TEXT,
                status TEXT
            )"""
        }

        for nome_tabella, schema in tabelle_gestionali.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {nome_tabella} {schema}")

        # --- Schema Migration: Assicura che la colonna Matricola esista ---
        # Questo approccio è più robusto rispetto a cancellare e ricreare.
        # Controlla le colonne esistenti nella tabella 'contatti'.
        cursor.execute("PRAGMA table_info(contatti)")
        colonne_esistenti = [info[1] for info in cursor.fetchall()]

        # Se 'Matricola' non è tra le colonne, la aggiunge.
        if "Matricola" not in colonne_esistenti:
            print("Aggiornamento dello schema: aggiunta della colonna 'Matricola' alla tabella 'contatti'...")
            cursor.execute("ALTER TABLE contatti ADD COLUMN Matricola TEXT")
            print("Schema aggiornato con successo.")

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