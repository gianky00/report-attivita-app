"""
Configurazione centralizzata dell'applicazione.
Gestisce il caricamento dei segreti, la validazione dei percorsi e i lock di sistema.
"""

import sys
import threading
from pathlib import Path

import toml
from core.logging import get_logger

logger = get_logger(__name__)

# --- CARICAMENTO CONFIGURAZIONE ---
SECRETS_PATH = Path(".streamlit/secrets.toml")

try:

    secrets = toml.loads(SECRETS_PATH.read_text(encoding="utf-8"))

except FileNotFoundError:

    # Se siamo in fase di test, non uscire ma usa un dizionario vuoto

    if "pytest" in sys.modules or "unittest" in sys.modules:

        logger.warning(
            f"File '{SECRETS_PATH}' non trovato. Procedo con configurazione vuota per i test."
        )

        secrets = {}

    else:

        logger.critical(
            f"File '{SECRETS_PATH}' non trovato. L'applicazione non può partire."
        )

        sys.exit(1)

except Exception as e:

    if "pytest" in sys.modules or "unittest" in sys.modules:

        secrets = {}

    else:

        logger.critical(f"Errore durante il caricamento di '{SECRETS_PATH}': {e}")

        sys.exit(1)


# --- VALIDAZIONE E PATHS ---

REQUIRED_KEYS = [
    "path_storico_db",
    "path_gestionale",
    "path_giornaliera_base",
    "path_attivita_programmate",
]


def validate_config(conf: dict):
    """Verifica la presenza di tutte le chiavi obbligatorie e la validità dei percorsi."""

    if not conf and ("pytest" in sys.modules or "unittest" in sys.modules):

        return

    missing = [k for k in REQUIRED_KEYS if k not in conf]

    if missing:
        logger.critical(
            f"Chiavi di configurazione mancanti in 'secrets.toml': {missing}"
        )
        sys.exit(1)

    # Verifica esistenza percorsi (warning se non esistono, ma non blocca l'avvio)
    for key in REQUIRED_KEYS:
        path = Path(conf[key])
        if not path.exists():
            logger.warning(f"Il percorso configurato per '{key}' non esiste: {path}")


validate_config(secrets)

# Esportazione costanti con fallback per i test
PATH_STORICO_DB = secrets.get("path_storico_db", "")
PATH_GESTIONALE = secrets.get("path_gestionale", "")
PATH_GIORNALIERA_BASE = secrets.get("path_giornaliera_base", "")
PATH_ATTIVITA_PROGRAMMATE = secrets.get("path_attivita_programmate", "")

# Percorso Knowledge Core (locale al progetto)
PATH_KNOWLEDGE_CORE = "knowledge_core.json"

# --- SPREADSHEET & EMAIL ---
NOME_FOGLIO_RISPOSTE = secrets.get(
    "nome_foglio_risposte", "Report Attività Giornaliera (Risposte)"
)
EMAIL_DESTINATARIO = secrets.get("email_destinatario", "gianky.allegretti@gmail.com")

# Gestione liste CC
email_cc_string = secrets.get("email_cc", "")
EMAIL_CC = [e.strip() for e in email_cc_string.split(",") if e.strip()]

# --- THREADING LOCKS ---
EXCEL_LOCK = threading.Lock()
OUTLOOK_LOCK = threading.Lock()


# --- FUNZIONI HELPER ---


def get_attivita_programmate_path() -> str:
    """Restituisce il percorso al file delle attività programmate."""

    return str(PATH_ATTIVITA_PROGRAMMATE)


def get_storico_db_path() -> str:
    """Restituisce il percorso allo storico DB."""

    return str(PATH_STORICO_DB)


def get_gestionale_path() -> str:
    """Restituisce il percorso al file gestionale."""

    return str(PATH_GESTIONALE)
