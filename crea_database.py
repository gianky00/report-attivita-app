
import sqlite3
import os
import pandas as pd
import bcrypt
import datetime
import shutil
import warnings
import re

def is_valid_bcrypt_hash(h):
    """Controlla se una stringa ha il formato di un hash bcrypt valido."""
    if not isinstance(h, str):
        return False
    # Regex per un hash bcrypt: es. $2b$12$E6e.gJ4.e/9nJ0.FlzAF8.
    bcrypt_pattern = re.compile(r'^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$')
    return bcrypt_pattern.match(h) is not None

# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*."
)

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"

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
            )""",
            "report_da_validare": """(
                id_report TEXT PRIMARY KEY NOT NULL,
                pdl TEXT,
                descrizione_attivita TEXT,
                matricola_tecnico TEXT,
                nome_tecnico TEXT,
                stato_attivita TEXT,
                testo_report TEXT,
                data_compilazione TEXT,
                data_riferimento_attivita TEXT
            )""",
            "relazioni": """(
                id_relazione TEXT PRIMARY KEY NOT NULL,
                data_intervento TEXT,
                tecnico_compilatore TEXT,
                partner TEXT,
                ora_inizio TEXT,
                ora_fine TEXT,
                corpo_relazione TEXT,
                stato TEXT,
                timestamp_invio TEXT,
                id_validatore TEXT,
                timestamp_validazione TEXT
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

def check_and_recreate_db_if_needed():
    """
    Controlla se il DB esiste e se ha lo schema corretto (verificando la PK della tabella contatti).
    Se lo schema è obsoleto, crea un backup del vecchio DB e lo elimina, forzando la ricreazione.
    """
    if not os.path.exists(DB_NAME):
        print("Database non trovato. Verrà creato.")
        return # Il DB non esiste, quindi verrà creato da zero

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Controlla se la tabella 'contatti' esiste prima di ispezionarla
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contatti';")
        if cursor.fetchone() is None:
            print("Tabella 'contatti' non trovata. Il database verrà ricreato.")
            # La tabella non esiste, quindi lo schema è incompleto.
            # Non c'è bisogno di fare un backup se manca la tabella principale.
            conn.close()
            os.remove(DB_NAME)
            print(f"File '{DB_NAME}' rimosso.")
            return

        # Ispeziona la tabella 'contatti' per vedere se 'Matricola' è una PK
        cursor.execute("PRAGMA table_info(contatti);")
        columns_info = cursor.fetchall()

        is_pk = False
        for col in columns_info:
            # col[1] è il nome della colonna, col[5] è 1 se è parte della PK
            if col[1] == 'Matricola' and col[5] == 1:
                is_pk = True
                break

        if not is_pk:
            print("ERRORE: Schema del database obsoleto rilevato (manca PK su 'contatti').")
            conn.close() # Chiudi la connessione prima di manipolare il file

            # Crea un backup
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{DB_NAME}.backup_{timestamp}"
            shutil.copy2(DB_NAME, backup_name)
            print(f"Backup del database corrente creato come '{backup_name}'.")

            # Rimuovi il vecchio DB per forzare la ricreazione
            os.remove(DB_NAME)
            print(f"Database obsoleto '{DB_NAME}' rimosso. Verrà ricreato con lo schema corretto.")

    except sqlite3.Error as e:
        print(f"Errore durante il controllo dello schema del database: {e}")
        # Se c'è un errore, potrebbe essere corrotto. Proviamo a ricrearlo.
        if conn:
            conn.close()
        if os.path.exists(DB_NAME):
             os.remove(DB_NAME)
        print(f"Database '{DB_NAME}' rimosso a causa di un errore.")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("Avvio dello script di creazione/aggiornamento del database...")
    check_and_recreate_db_if_needed()
    crea_tabelle_se_non_esistono()
    print("\nOperazione completata.")
