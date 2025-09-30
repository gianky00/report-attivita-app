import sqlite3
import os

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"

def crea_tabella():
    """
    Crea e ottimizza le tabelle del database con la nuova struttura per il sync v2.0.
    La funzione è idempotente.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Abilita il supporto per le chiavi esterne
        cursor.execute("PRAGMA foreign_keys = ON;")

        # --- TABELLA ATTIVITA' PROGRAMMATE (Schema v2.0) ---
        # Dropping the old table to ensure the new schema with PRIMARY KEY is applied correctly.
        # This is safe because the data will be re-synced from the Excel file.
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

        # New schema based on validated Excel headers
        cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            PdL TEXT PRIMARY KEY NOT NULL,
            FERM TEXT,
            MANUT TEXT,
            PS TEXT,
            AREA TEXT,
            IMP TEXT,
            DESCRIZIONE_ATTIVITA TEXT,
            LUN TEXT,
            MAR TEXT,
            MER TEXT,
            GIO TEXT,
            VEN TEXT,
            STATO_PdL TEXT,
            ESE TEXT,
            SAIT TEXT,
            PONTEROSSO TEXT,
            STATO_ATTIVITA TEXT,
            DATA_CONTROLLO TEXT,
            PERSONALE_IMPIEGATO TEXT,
            PO TEXT,
            AVVISO TEXT,
            Storico TEXT,
            row_last_modified DATETIME NOT NULL
        );
        """)
        print(f"Tabella '{TABLE_NAME}' creata con il nuovo schema v2.0.")

        # --- TABELLE GESTIONALI (invariate) ---
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

        # --- CREAZIONE INDICI PER OTTIMIZZAZIONE QUERY (Schema v2.0) ---
        # L'indice su PdL non è più necessario perché è la PRIMARY KEY.
        indici = {
            "idx_attivita_stato": f"CREATE INDEX IF NOT EXISTS idx_attivita_stato ON {TABLE_NAME}(STATO_ATTIVITA);",
            "idx_attivita_area": f"CREATE INDEX IF NOT EXISTS idx_attivita_area ON {TABLE_NAME}(AREA);",
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

        # --- SCHEMA MIGRATION (pulizia) ---
        # La vecchia colonna 'db_last_modified' non è più necessaria.
        # La logica di migrazione per 'Matricola' è ancora utile.
        def add_column_if_not_exists(table, column, col_type):
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [info[1] for info in cursor.fetchall()]
            if column not in existing_columns:
                print(f"Aggiornamento schema: aggiunta colonna '{column}' a '{table}'...")
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                print("Schema aggiornato.")

        add_column_if_not_exists("contatti", "Matricola", "TEXT")

        conn.commit()
        print(f"Database '{DB_NAME}' e tabelle ottimizzate pronti per l'uso (Schema v2.0).")

    except sqlite3.Error as e:
        print(f"Errore durante la creazione/ottimizzazione del database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Rimuove il vecchio database per forzare la ricreazione con il nuovo schema.
    if os.path.exists(DB_NAME):
        print(f"Rimozione del database esistente '{DB_NAME}' per applicare il nuovo schema.")
        os.remove(DB_NAME)
    crea_tabella()