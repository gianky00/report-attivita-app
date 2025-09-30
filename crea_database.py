import sqlite3
import os
import pandas as pd
import bcrypt

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
EXCEL_GESTIONALE = "Gestionale_Tecnici.xlsx"

# Mappa Nomi Foglio Excel -> Nomi Tabella DB e Chiavi Primarie
SHEET_TABLE_MAP = {
    "Contatti": ("contatti", "Matricola"),
    "Turni": ("turni", "ID_Turno"),
    "Prenotazioni": ("prenotazioni", "ID_Prenotazione"),
    "Sostituzioni": ("sostituzioni", "ID_Richiesta"),
    "Notifiche": ("notifiche", "ID_Notifica"),
    "Bacheca": ("bacheca", "ID_Bacheca"),
    "Richieste Materiali": ("richieste_materiali", "ID_Richiesta"),
    "Richieste Assenze": ("richieste_assenze", "ID_Richiesta"),
    "Access Logs": ("access_logs", None) # Append-only, no PK needed
}

def is_valid_bcrypt_hash(h):
    """
    Verifica se una stringa è un hash bcrypt valido strutturalmente.
    Questo non garantisce che sia stato generato da bcrypt, ma esclude
    dati palesemente non validi come 'vuoto', ' ', o None.
    """
    if not isinstance(h, str):
        return False
    # I prefissi validi per bcrypt
    if not (h.startswith('$2a$') or h.startswith('$2b$') or h.startswith('$2y$')):
        return False
    # Un hash bcrypt ha una lunghezza standard di 60 caratteri
    if len(h) != 60:
        return False
    return True

def sync_excel_to_db():
    """
    Sincronizza TUTTI i fogli del file Gestionale_Tecnici.xlsx con il database,
    aggiornando le righe esistenti e inserendone di nuove (upsert).
    """
    if not os.path.exists(EXCEL_GESTIONALE):
        print(f"File gestionale '{EXCEL_GESTIONALE}' non trovato. Salto la sincronizzazione.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)

        # --- FASE 1: Creazione mappa Nome Cognome -> Matricola ---
        print("Creazione della mappa di conversione da Nome a Matricola...")
        nome_a_matricola = {}
        with pd.ExcelFile(EXCEL_GESTIONALE) as xls:
            if "Contatti" in xls.sheet_names:
                contatti_df = pd.read_excel(xls, sheet_name="Contatti")
                contatti_df.columns = [str(col).strip() for col in contatti_df.columns]
                contatti_df.dropna(subset=['Matricola', 'Nome Cognome'], inplace=True)
                contatti_df = contatti_df[contatti_df['Matricola'].astype(str).str.strip() != '']
                contatti_df = contatti_df[contatti_df['Nome Cognome'].astype(str).str.strip() != '']
                nome_a_matricola = pd.Series(contatti_df.Matricola.astype(str).values, index=contatti_df['Nome Cognome']).to_dict()
                print(f"Mappa creata con successo con {len(nome_a_matricola)} voci.")
            else:
                print("ERRORE: Foglio 'Contatti' non trovato. Impossibile procedere.")
                return

        with pd.ExcelFile(EXCEL_GESTIONALE) as xls:
            for sheet_name, (table_name, pk_col) in SHEET_TABLE_MAP.items():
                if sheet_name not in xls.sheet_names:
                    print(f"Avviso: Foglio '{sheet_name}' non trovato in {EXCEL_GESTIONALE}. Salto.")
                    continue

                print(f"--- Inizio sincronizzazione per '{sheet_name}' -> '{table_name}' ---")

                df = pd.read_excel(xls, sheet_name=sheet_name)
                df.columns = [str(col).strip() for col in df.columns]

                # Converte tutte le colonne in stringhe per evitare problemi di tipo con il DB
                for col in df.columns:
                    df[col] = df[col].astype(str).where(pd.notna(df[col]), None)

                # --- FASE 2: Trasformazione dati per Foreign Keys ---
                transformations = {
                    'prenotazioni': [('Nome Cognome', 'Matricola')],
                    'sostituzioni': [('Richiedente', 'Richiedente_Matricola'), ('Ricevente', 'Ricevente_Matricola')],
                    'notifiche': [('Destinatario', 'Destinatario_Matricola')],
                    'bacheca': [('Tecnico_Originale', 'Tecnico_Originale_Matricola'), ('Tecnico_Subentrante', 'Tecnico_Subentrante_Matricola')],
                    'richieste_materiali': [('Richiedente', 'Richiedente_Matricola')],
                    'richieste_assenze': [('Richiedente', 'Richiedente_Matricola')],
                    'validation_sessions': [('user_name', 'user_matricola')]
                }

                if table_name in transformations:
                    print(f"Applicazione trasformazioni per '{table_name}'...")
                    original_rows = len(df)
                    for old_col, new_col in transformations[table_name]:
                        if old_col in df.columns:
                            # Applica la mappa e gestisce i nomi non trovati (imposta a None)
                            df[new_col] = df[old_col].map(nome_a_matricola)
                            # Pulisce le righe dove non è stata trovata una matricola
                            df.dropna(subset=[new_col], inplace=True)
                            df = df.drop(columns=[old_col])

                    if len(df) < original_rows:
                        print(f"Attenzione: {original_rows - len(df)} righe in '{sheet_name}' sono state saltate per mappatura Nome->Matricola fallita.")

                # Gestione speciale per la tabella contatti per pulire i dati delle password
                if table_name == 'contatti':
                    # Validazione: La Matricola è obbligatoria e non può essere vuota.
                    original_rows = len(df)
                    df.dropna(subset=['Matricola'], inplace=True)
                    df = df[df['Matricola'].astype(str).str.strip() != '']

                    if len(df) < original_rows:
                        print(f"Attenzione: {original_rows - len(df)} righe sono state saltate perché prive di Matricola.")

                    # Rimuove la colonna 'Nome Cognome' se non è la PK (lo è Matricola ora)
                    # per evitare problemi di 'colonna duplicata' con lo schema.
                    if pk_col != 'Nome Cognome' and 'Nome Cognome' in df.columns:
                         # Questo non dovrebbe accadere con lo schema nuovo, ma è una sicurezza
                         pass


                    # Se esiste la vecchia colonna 'Password', la rimuoviamo perché non è sicura
                    if 'Password' in df.columns:
                        df = df.drop(columns=['Password'], errors='ignore')

                    # Se non esiste la colonna 'PasswordHash', la aggiungiamo vuota
                    if 'PasswordHash' not in df.columns:
                        df['PasswordHash'] = None
                    else:
                        # Pulisce e valida la colonna PasswordHash: qualsiasi valore non valido
                        # viene impostato a None per forzare il setup al primo login.
                        print("Validazione degli hash delle password...")
                        df['PasswordHash'] = df['PasswordHash'].apply(
                            lambda h: h if is_valid_bcrypt_hash(h) else None
                        )
                        print("Validazione completata.")

                df.to_sql(f"{table_name}_temp", conn, if_exists='replace', index=False)

                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name}_temp")
                rows = cursor.fetchall()
                cols = [description[0] for description in cursor.description]

                if not pk_col: # Se non c'è chiave primaria, facciamo solo append
                    df.to_sql(table_name, conn, if_exists='append', index=False)
                    print(f"Aggiunte {len(df)} righe a '{table_name}'.")
                else:
                    upserted_count = 0
                    for row in rows:
                        row_dict = dict(zip(cols, row))

                        # Costruzione dinamica della query di upsert
                        update_clause = ", ".join([f'"{col}" = ?' for col in cols if col != pk_col])
                        cols_clause = ", ".join([f'"{col}"' for col in cols])
                        placeholders = ", ".join(['?'] * len(cols))

                        sql = f"""
                        INSERT INTO {table_name} ({cols_clause})
                        VALUES ({placeholders})
                        ON CONFLICT({pk_col}) DO UPDATE SET
                        {update_clause};
                        """

                        values_insert = list(row_dict.values())
                        values_update = [v for k, v in row_dict.items() if k != pk_col]

                        cursor.execute(sql, values_insert + values_update)
                        upserted_count += 1

                    print(f"Sincronizzate {upserted_count} righe per la tabella '{table_name}'.")

                cursor.execute(f"DROP TABLE {table_name}_temp")
                conn.commit()
                print(f"--- Sincronizzazione per '{table_name}' completata ---")

    except Exception as e:
        print(f"Errore critico durante la sincronizzazione da Excel a DB: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def crea_tabelle_se_non_esistono():
    """
    Crea tutte le tabelle necessarie nel database se non esistono già.
    Questo previene la perdita di dati ma assicura che lo schema sia completo.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        tabelle_gestionali = {
            "contatti": """(
                Matricola TEXT PRIMARY KEY NOT NULL,
                "Nome Cognome" TEXT NOT NULL UNIQUE,
                Ruolo TEXT,
                PasswordHash TEXT,
                "Link Attività" TEXT,
                "2FA_Secret" TEXT
            )""",
            "turni": """(ID_Turno TEXT PRIMARY KEY NOT NULL, Descrizione TEXT, Data TEXT, OrarioInizio TEXT, OrarioFine TEXT, PostiTecnico INTEGER, PostiAiutante INTEGER, Tipo TEXT)""",
            "prenotazioni": """(
                ID_Prenotazione TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Matricola TEXT NOT NULL,
                RuoloOccupato TEXT,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "sostituzioni": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Richiedente_Matricola TEXT NOT NULL,
                Ricevente_Matricola TEXT NOT NULL,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Richiedente_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE,
                FOREIGN KEY (Ricevente_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "notifiche": """(
                ID_Notifica TEXT PRIMARY KEY NOT NULL,
                Timestamp TEXT,
                Destinatario_Matricola TEXT NOT NULL,
                Messaggio TEXT,
                Stato TEXT,
                Link_Azione TEXT,
                FOREIGN KEY (Destinatario_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "bacheca": """(
                ID_Bacheca TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Tecnico_Originale_Matricola TEXT NOT NULL,
                Ruolo_Originale TEXT,
                Timestamp_Pubblicazione TEXT,
                Stato TEXT,
                Tecnico_Subentrante_Matricola TEXT,
                Timestamp_Assegnazione TEXT,
                FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Tecnico_Originale_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "richieste_materiali": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                Richiedente_Matricola TEXT NOT NULL,
                Timestamp TEXT,
                Stato TEXT,
                Dettagli TEXT,
                FOREIGN KEY (Richiedente_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "richieste_assenze": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                Richiedente_Matricola TEXT NOT NULL,
                Timestamp TEXT,
                Tipo_Assenza TEXT,
                Data_Inizio TEXT,
                Data_Fine TEXT,
                Note TEXT,
                Stato TEXT,
                FOREIGN KEY (Richiedente_Matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "access_logs": """(timestamp TEXT, username TEXT, status TEXT)""",
            "validation_sessions": """(
                session_id TEXT PRIMARY KEY NOT NULL,
                user_matricola TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (user_matricola) REFERENCES contatti(Matricola) ON DELETE CASCADE
            )"""
        }

        for nome_tabella, schema in tabelle_gestionali.items():
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{nome_tabella}';")
            if cursor.fetchone() is None:
                print(f"Tabella '{nome_tabella}' non trovata. Creazione in corso...")
                cursor.execute(f"CREATE TABLE {nome_tabella} {schema}")
                print(f"Tabella '{nome_tabella}' creata.")

        # Tabella per il sincronizzatore v2
        attivita_schema = """(
            "PdL" TEXT PRIMARY KEY NOT NULL,
            "FERM" TEXT, "MANUT" TEXT, "PS" TEXT, "AREA" TEXT, "IMP" TEXT,
            "DESCRIZIONE_ATTIVITA" TEXT, "LUN" TEXT, "MAR" TEXT, "MER" TEXT,
            "GIO" TEXT, "VEN" TEXT, "STATO_PdL" TEXT, "ESE" TEXT, "SAIT" TEXT,
            "PONTEROSSO" TEXT, "STATO_ATTIVITA" TEXT, "DATA_CONTROLLO" TEXT,
            "PERSONALE_IMPIEGATO" TEXT, "PO" TEXT, "AVVISO" TEXT,
            "row_last_modified" TEXT, "source_sheet" TEXT, "Storico" TEXT,
            "db_last_modified" TEXT
        )"""
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='attivita_programmate';")
        if cursor.fetchone() is None:
            print("Tabella 'attivita_programmate' non trovata. Creazione in corso...")
            cursor.execute(f"CREATE TABLE attivita_programmate {attivita_schema}")
            print("Tabella 'attivita_programmate' creata.")
        else:
            # Logica di migrazione per aggiungere la colonna se non esiste
            cursor.execute("PRAGMA table_info(attivita_programmate)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'db_last_modified' not in columns:
                print("Aggiunta della colonna 'db_last_modified' alla tabella esistente...")
                cursor.execute("ALTER TABLE attivita_programmate ADD COLUMN db_last_modified TEXT;")
                print("Colonna 'db_last_modified' aggiunta.")

        conn.commit()
        print("Verifica e creazione tabelle completata.")

    except sqlite3.Error as e:
        print(f"Errore durante la creazione/verifica delle tabelle: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Avvio dello script di creazione/aggiornamento del database...")
    crea_tabelle_se_non_esistono()
    print("\nAvvio della sincronizzazione completa da Excel a DB...")
    sync_excel_to_db()
    print("\nOperazione completata.")