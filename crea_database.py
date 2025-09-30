import sqlite3
import os

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"

def crea_tabella():
    """
    Crea e ottimizza le tabelle del database con chiavi esterne e indici.
    La funzione è idempotente: non farà nulla se le tabelle esistono già.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Abilita il supporto per le chiavi esterne, essenziale per l'integrità dei dati
        cursor.execute("PRAGMA foreign_keys = ON;")

        # --- TABELLA ATTIVITA' PROGRAMMATE ---
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            PdL TEXT NOT NULL,
            Impianto TEXT,
            Descrizione TEXT,
            Stato_OdL TEXT,
            Lunedì TEXT, Martedì TEXT, Mercoledì TEXT, Giovedì TEXT, Venerdì TEXT,
            TCL TEXT,
            Area TEXT,
            GiorniProgrammati TEXT,
            Stato TEXT,
            Storico TEXT
        );
        """)

        # --- TABELLE GESTIONALI CON VINCOLI ---
        tabelle_gestionali = {
            "contatti": """(
                "Nome Cognome" TEXT PRIMARY KEY NOT NULL,
                Ruolo TEXT,
                PasswordHash TEXT,
                "Link Attività" TEXT,
                "2FA_Secret" TEXT,
                Matricola TEXT
            )""",
            "turni": """(
                ID_Turno TEXT PRIMARY KEY NOT NULL,
                Descrizione TEXT,
                Data TEXT,
                OrarioInizio TEXT,
                OrarioFine TEXT,
                PostiTecnico INTEGER,
                PostiAiutante INTEGER,
                Tipo TEXT
            )""",
            "prenotazioni": """(
                ID_Prenotazione TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                "Nome Cognome" TEXT NOT NULL,
                RuoloOccupato TEXT,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY ("Nome Cognome") REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
            "sostituzioni": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Richiedente TEXT NOT NULL,
                Ricevente TEXT NOT NULL,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE,
                FOREIGN KEY (Ricevente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
            "notifiche": """(
                ID_Notifica TEXT PRIMARY KEY NOT NULL,
                Timestamp TEXT,
                Destinatario TEXT NOT NULL,
                Messaggio TEXT,
                Stato TEXT,
                Link_Azione TEXT,
                FOREIGN KEY (Destinatario) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
            "bacheca": """(
                ID_Bacheca TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Tecnico_Originale TEXT NOT NULL,
                Ruolo_Originale TEXT,
                Timestamp_Pubblicazione TEXT,
                Stato TEXT,
                Tecnico_Subentrante TEXT,
                Timestamp_Assegnazione TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Tecnico_Originale) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
            "richieste_materiali": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                Richiedente TEXT NOT NULL,
                Timestamp TEXT,
                Stato TEXT,
                Dettagli TEXT,
                FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
            "richieste_assenze": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                Richiedente TEXT NOT NULL,
                Timestamp TEXT,
                Tipo_Assenza TEXT,
                Data_Inizio TEXT,
                Data_Fine TEXT,
                Note TEXT,
                Stato TEXT,
                FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )""",
             "access_logs": """(
                timestamp TEXT,
                username TEXT,
                status TEXT
            )""",
            "validation_sessions": """(
                session_id TEXT PRIMARY KEY NOT NULL,
                user_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (user_name) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE
            )"""
        }

        for nome_tabella, schema in tabelle_gestionali.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {nome_tabella} {schema}")

        # --- CREAZIONE INDICI PER OTTIMIZZAZIONE QUERY ---
        indici = {
            "idx_attivita_pdl": f"CREATE INDEX IF NOT EXISTS idx_attivita_pdl ON {TABLE_NAME}(PdL);",
            "idx_attivita_stato": f"CREATE INDEX IF NOT EXISTS idx_attivita_stato ON {TABLE_NAME}(Stato);",
            "idx_attivita_area_tcl": f"CREATE INDEX IF NOT EXISTS idx_attivita_area_tcl ON {TABLE_NAME}(Area, TCL);",
            "idx_turni_tipo_data": "CREATE INDEX IF NOT EXISTS idx_turni_tipo_data ON turni(Tipo, Data);",
            "idx_prenotazioni_turno_utente": "CREATE INDEX IF NOT EXISTS idx_prenotazioni_turno_utente ON prenotazioni(ID_Turno, \"Nome Cognome\");",
            "idx_access_logs_timestamp": "CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp);",
            "idx_access_logs_username": "CREATE INDEX IF NOT EXISTS idx_access_logs_username ON access_logs(username);",
            "idx_validation_sessions_user_status": "CREATE INDEX IF NOT EXISTS idx_validation_sessions_user_status ON validation_sessions(user_name, status);"
        }

        for nome_indice, statement in indici.items():
            cursor.execute(statement)

        # --- TABELLA METADATI DI SINCRONIZZAZIONE ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        # --- SCHEMA MIGRATION ---
        def add_column_if_not_exists(table, column, col_type):
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [info[1] for info in cursor.fetchall()]
            if column not in existing_columns:
                print(f"Aggiornamento schema: aggiunta colonna '{column}' a '{table}'...")
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                print("Schema aggiornato.")

        add_column_if_not_exists("contatti", "Matricola", "TEXT")
        add_column_if_not_exists(TABLE_NAME, "db_last_modified", "TEXT")

        conn.commit()
        print(f"Database '{DB_NAME}' e tabelle ottimizzate pronti per l'uso.")

    except sqlite3.Error as e:
        print(f"Errore durante la creazione/ottimizzazione del database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    crea_tabella()