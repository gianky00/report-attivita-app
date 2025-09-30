import sqlite3
import os
import pandas as pd
import bcrypt

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
EXCEL_GESTIONALE = "Gestionale_Tecnici.xlsx"

# Mappa Nomi Foglio Excel -> Nomi Tabella DB e Chiavi Primarie
SHEET_TABLE_MAP = {
    "Contatti": ("contatti", "Nome Cognome"),
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

                # Gestione speciale per la tabella contatti per pulire i dati delle password
                if table_name == 'contatti':
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
                        ON CONFLICT("{pk_col}") DO UPDATE SET
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
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{nome_tabella}';")
            if cursor.fetchone() is None:
                print(f"Tabella '{nome_tabella}' non trovata. Creazione in corso...")
                cursor.execute(f"CREATE TABLE {nome_tabella} {schema}")
                print(f"Tabella '{nome_tabella}' creata.")

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