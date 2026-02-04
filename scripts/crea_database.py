"""
Script per l'inizializzazione e l'aggiornamento dello schema del database SQLite.
Garantisce la creazione di tutte le tabelle necessarie e dei vincoli di integrità.
"""

import re
import sqlite3
import sys
import warnings
from pathlib import Path

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent))
from src.core.logging import get_logger

logger = get_logger(__name__)


def is_valid_bcrypt_hash(h: str) -> bool:
    """Controlla se una stringa ha il formato di un hash bcrypt valido."""
    if not isinstance(h, str):
        return False
    bcrypt_pattern = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
    return bcrypt_pattern.match(h) is not None


# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*.",
)

# --- CONFIGURAZIONE ---
BASE_DIR = Path(__file__).parent.parent
DB_NAME = BASE_DIR / "schedario.db"


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
            "esclusioni_assegnamenti": """(
                id_esclusione INTEGER PRIMARY KEY AUTOINCREMENT,
                matricola_escludente TEXT NOT NULL,
                id_attivita TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (matricola_escludente)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
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
                Matricola TEXT NOT NULL,
                RuoloOccupato TEXT,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno)
                    REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "sostituzioni": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                ID_Turno TEXT NOT NULL,
                Richiedente_Matricola TEXT NOT NULL,
                Ricevente_Matricola TEXT NOT NULL,
                Timestamp TEXT,
                FOREIGN KEY (ID_Turno)
                    REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Richiedente_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE,
                FOREIGN KEY (Ricevente_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "notifiche": """(
                ID_Notifica TEXT PRIMARY KEY NOT NULL,
                Timestamp TEXT,
                Destinatario_Matricola TEXT NOT NULL,
                Messaggio TEXT,
                Stato TEXT,
                Link_Azione TEXT,
                FOREIGN KEY (Destinatario_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
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
                FOREIGN KEY (ID_Turno)
                    REFERENCES turni(ID_Turno) ON DELETE CASCADE,
                FOREIGN KEY (Tecnico_Originale_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "richieste_materiali": """(
                ID_Richiesta TEXT PRIMARY KEY NOT NULL,
                Richiedente_Matricola TEXT NOT NULL,
                Timestamp TEXT,
                Stato TEXT,
                Dettagli TEXT,
                FOREIGN KEY (Richiedente_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
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
                FOREIGN KEY (Richiedente_Matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
            )""",
            "access_logs": """(timestamp TEXT, username TEXT, status TEXT)""",
            "validation_sessions": """(
                session_id TEXT PRIMARY KEY NOT NULL,
                user_matricola TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (user_matricola)
                    REFERENCES contatti(Matricola) ON DELETE CASCADE
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
            )""",
            "report_interventi": """(
                id_report TEXT PRIMARY KEY NOT NULL,
                pdl TEXT,
                descrizione_attivita TEXT,
                matricola_tecnico TEXT,
                nome_tecnico TEXT,
                stato_attivita TEXT,
                testo_report TEXT,
                data_compilazione TEXT,
                data_riferimento_attivita TEXT,
                timestamp_validazione TEXT
            )""",
            "storico_richieste_materiali": """(
                id_storico INTEGER PRIMARY KEY AUTOINCREMENT,
                id_richiesta TEXT NOT NULL,
                richiedente_matricola TEXT,
                nome_richiedente TEXT,
                timestamp_richiesta TEXT,
                dettagli_richiesta TEXT,
                timestamp_approvazione TEXT
            )""",
            "storico_richieste_assenze": """(
                id_storico INTEGER PRIMARY KEY AUTOINCREMENT,
                id_richiesta TEXT NOT NULL,
                richiedente_matricola TEXT,
                nome_richiedente TEXT,
                timestamp_richiesta TEXT,
                tipo_assenza TEXT,
                data_inizio TEXT,
                data_fine TEXT,
                note TEXT,
                timestamp_approvazione TEXT
            )""",
            "shift_logs": """(
                ID_Modifica TEXT PRIMARY KEY NOT NULL,
                Timestamp TEXT,
                ID_Turno TEXT,
                Azione TEXT,
                UtenteOriginale TEXT,
                UtenteSubentrante TEXT,
                EseguitoDa TEXT
            )""",
        }

        for nome_tabella, schema in tabelle_gestionali.items():
            cursor.execute(
                "SELECT name FROM sqlite_master "
                f"WHERE type='table' AND name='{nome_tabella}';"
            )
            if cursor.fetchone() is None:
                logger.info(
                    f"Tabella '{nome_tabella}' non trovata. Creazione in corso..."
                )
                cursor.execute(f"CREATE TABLE {nome_tabella} {schema}")
                logger.info(f"Tabella '{nome_tabella}' creata.")

        conn.commit()
        logger.info("Verifica e creazione tabelle completata.")

    except sqlite3.Error as e:
        logger.error(
            f"Errore durante la creazione/verifica delle tabelle: {e}", exc_info=True
        )
    finally:
        if conn:
            conn.close()


def check_and_recreate_db_if_needed():
    """Controlla se il DB esiste. Se non esiste, lo crea."""
    if not DB_NAME.exists():
        logger.warning("Database non trovato. Verrà creato.")
        crea_tabelle_se_non_esistono()


if __name__ == "__main__":
    logger.info("Avvio dello script di creazione/aggiornamento del database...")
    check_and_recreate_db_if_needed()
    crea_tabelle_se_non_esistono()
    logger.info("Operazione completata con successo.")
