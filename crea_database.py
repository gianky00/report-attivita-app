import sqlite3
import os
import pandas as pd

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"
EXCEL_GESTIONALE = "Gestionale_Tecnici.xlsx"


def sincronizza_contatti_da_excel():
    """
    Legge i dati dal file Gestionale_Tecnici.xlsx e li sincronizza
    con la tabella 'contatti' nel database SQLite, inserendo solo i nuovi utenti.
    """
    if not os.path.exists(EXCEL_GESTIONALE):
        print(f"File gestionale '{EXCEL_GESTIONALE}' non trovato. Salto la sincronizzazione dei contatti.")
        return

    conn = None
    try:
        # Leggi i dati da Excel, assicurandoti che tutte le colonne siano stringhe per evitare errori di tipo
        df_excel = pd.read_excel(EXCEL_GESTIONALE, sheet_name="Contatti", dtype=str)
        df_excel.columns = [str(col).strip() for col in df_excel.columns]

        required_cols = ["Nome Cognome", "Ruolo", "Matricola"]
        if not all(col in df_excel.columns for col in required_cols):
            print(f"Errore: Il file Excel deve contenere le colonne {required_cols}. Sincronizzazione annullata.")
            return

        # Pulisce e prepara i dati
        df_excel['Matricola'] = df_excel['Matricola'].str.strip()
        df_excel.dropna(subset=['Matricola'], inplace=True)
        df_excel = df_excel[df_excel['Matricola'] != '']

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        utenti_inseriti = 0
        for _, row_excel in df_excel.iterrows():
            matricola = row_excel.get('Matricola')
            if not matricola or matricola.lower() == 'nan':
                continue

            cursor.execute("SELECT Matricola FROM contatti WHERE Matricola = ?", (matricola,))
            if cursor.fetchone() is None:
                # L'utente non esiste, lo inseriamo
                nome_cognome = row_excel['Nome Cognome']
                ruolo = row_excel['Ruolo']

                # Inseriamo None per PasswordHash e 2FA_Secret, verranno impostati al primo login
                user_data = (nome_cognome, ruolo, None, None, matricola)

                cursor.execute("""
                    INSERT INTO contatti ("Nome Cognome", Ruolo, PasswordHash, "2FA_Secret", Matricola)
                    VALUES (?, ?, ?, ?, ?)
                """, user_data)
                print(f"Nuovo utente inserito: {nome_cognome} (Matricola: {matricola})")
                utenti_inseriti += 1

        conn.commit()
        print(f"Sincronizzazione dei contatti completata. {utenti_inseriti} nuovi utenti aggiunti.")

    except FileNotFoundError:
        print(f"File '{EXCEL_GESTIONALE}' non trovato.")
    except Exception as e:
        print(f"Errore durante la sincronizzazione dei contatti: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def crea_tabella():
    """
    Crea e ottimizza le tabelle del database con la nuova struttura per il sync v2.1.
    Aggiunge la colonna 'source_sheet' per la gestione multi-foglio.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")

        # --- TABELLA ATTIVITA' PROGRAMMATE (Schema v2.1) ---
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

        # Aggiunta la colonna 'source_sheet'
        cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            PdL TEXT PRIMARY KEY NOT NULL,
            source_sheet TEXT NOT NULL,
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
        print(f"Tabella '{TABLE_NAME}' creata con il nuovo schema v2.1 (con source_sheet).")

        # --- TABELLE GESTIONALI (invariate) ---
        tabelle_gestionali = {
            "contatti": """("Nome Cognome" TEXT PRIMARY KEY NOT NULL, Ruolo TEXT, PasswordHash TEXT, "Link Attività" TEXT, "2FA_Secret" TEXT, Matricola TEXT)""",
            "turni": """(ID_Turno TEXT PRIMARY KEY NOT NULL, Descrizione TEXT, Data TEXT, OrarioInizio TEXT, OrarioFine TEXT, PostiTecnico INTEGER, PostiAiutante INTEGER, Tipo TEXT)""",
            "prenotazioni": """(ID_Prenotazione TEXT PRIMARY KEY NOT NULL, ID_Turno TEXT NOT NULL, "Nome Cognome" TEXT NOT NULL, RuoloOccupato TEXT, Timestamp TEXT, FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE, FOREIGN KEY ("Nome Cognome") REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "sostituzioni": """(ID_Richiesta TEXT PRIMARY KEY NOT NULL, ID_Turno TEXT NOT NULL, Richiedente TEXT NOT NULL, Ricevente TEXT NOT NULL, Timestamp TEXT, FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE, FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE, FOREIGN KEY (Ricevente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "notifiche": """(ID_Notifica TEXT PRIMARY KEY NOT NULL, Timestamp TEXT, Destinatario TEXT NOT NULL, Messaggio TEXT, Stato TEXT, Link_Azione TEXT, FOREIGN KEY (Destinatario) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "bacheca": """(ID_Bacheca TEXT PRIMARY KEY NOT NULL, ID_Turno TEXT NOT NULL, Tecnico_Originale TEXT NOT NULL, Ruolo_Originale TEXT, Timestamp_Pubblicazione TEXT, Stato TEXT, Tecnico_Subentrante TEXT, Timestamp_Assegnazione TEXT, FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE, FOREIGN KEY (Tecnico_Originale) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "richieste_materiali": """(ID_Richiesta TEXT PRIMARY KEY NOT NULL, Richiedente TEXT NOT NULL, Timestamp TEXT, Stato TEXT, Dettagli TEXT, FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "richieste_assenze": """(ID_Richiesta TEXT PRIMARY KEY NOT NULL, Richiedente TEXT NOT NULL, Timestamp TEXT, Tipo_Assenza TEXT, Data_Inizio TEXT, Data_Fine TEXT, Note TEXT, Stato TEXT, FOREIGN KEY (Richiedente) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)""",
            "access_logs": """(timestamp TEXT, username TEXT, status TEXT)""",
            "validation_sessions": """(session_id TEXT PRIMARY KEY NOT NULL, user_name TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY (user_name) REFERENCES contatti("Nome Cognome") ON DELETE CASCADE)"""
        }

        for nome_tabella, schema in tabelle_gestionali.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {nome_tabella} {schema}")

        # --- CREAZIONE INDICI PER OTTIMIZZAZIONE QUERY (Schema v2.1) ---
        indici = {
            "idx_attivita_sheet": f"CREATE INDEX IF NOT EXISTS idx_attivita_sheet ON {TABLE_NAME}(source_sheet);",
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

        def add_column_if_not_exists(table, column, col_type):
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [info[1] for info in cursor.fetchall()]
            if column not in existing_columns:
                print(f"Aggiornamento schema: aggiunta colonna '{column}' a '{table}'...")
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                print("Schema aggiornato.")

        add_column_if_not_exists("contatti", "Matricola", "TEXT")

        conn.commit()
        print(f"Database '{DB_NAME}' e tabelle ottimizzate pronti per l'uso (Schema v2.1).")

    except sqlite3.Error as e:
        print(f"Errore durante la creazione/ottimizzazione del database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # La logica ora è: crea le tabelle se non esistono, poi sincronizza i contatti.
    # Non rimuove più il DB se esiste, per preservare i dati esistenti.
    print("Avvio dello script di creazione/aggiornamento del database...")
    crea_tabella()
    print("\nAvvio della sincronizzazione dei contatti da Excel...")
    sincronizza_contatti_da_excel()
    print("\nOperazione completata.")