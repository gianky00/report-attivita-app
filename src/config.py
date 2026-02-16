"""
Configurazione centralizzata dell'applicazione.
Gestisce il caricamento dei segreti, la validazione dei percorsi e i lock di sistema.
"""

import datetime
import os
import sys
import threading
from pathlib import Path
from typing import Any

import toml

from constants import REQUIRED_CONFIG_KEYS
from core.logging import get_logger

logger = get_logger(__name__)

# --- UTILS PER PATH ---
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
IS_DOCKER = Path("/.dockerenv").exists() or os.environ.get("IS_DOCKER", "false").lower() == "true"


def resolve_path(raw_path: str) -> str:
    """
    Converte percorsi Windows/Assoluti in percorsi validi per l'ambiente corrente.
    In Docker, punta alla cartella di sincronizzazione locale montata su /mnt/network.
    """
    if not raw_path:
        return ""

    if IS_DOCKER:
        # Se siamo in Docker, cerchiamo di mappare il percorso sulla nostra cartella sync
        p = raw_path.replace("\\", "/")

        # Se il percorso contiene Giornaliere, ricostruiamo la struttura relativa
        if "Giornaliere" in p:
            # Estraiamo tutto cio' che segue 'Giornaliere' inclusa la parola stessa
            idx = p.find("Giornaliere")
            return str(Path("/mnt/network") / p[idx:])

        # Per i file radice (Database_Report_Attivita.xlsm, ecc)
        filename = Path(p).name
        root_file = Path("/mnt/network") / filename
        if root_file.exists():
            return str(root_file)

        return str(Path("/mnt/network") / filename)

    return str(Path(raw_path))


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
        logger.critical(f"File '{SECRETS_PATH}' non trovato. L'applicazione non può partire.")

        sys.exit(1)

except Exception as e:
    if "pytest" in sys.modules or "unittest" in sys.modules:
        secrets = {}

    else:
        logger.critical(f"Errore durante il caricamento di '{SECRETS_PATH}': {e}")

        sys.exit(1)


# --- VALIDAZIONE E PATHS ---


def validate_config(conf: dict[str, Any]) -> None:
    """Verifica la presenza di tutte le chiavi obbligatorie e la validità dei percorsi."""

    if not conf and ("pytest" in sys.modules or "unittest" in sys.modules):
        return

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in conf]

    if missing:
        logger.critical(f"Chiavi di configurazione mancanti in 'secrets.toml': {missing}")
        sys.exit(1)

    # Verifica esistenza percorsi (warning se non esistono, ma non blocca l'avvio)
    for key in REQUIRED_CONFIG_KEYS:
        path = Path(resolve_path(conf[key]))
        if not path.exists():
            logger.warning(f"Il percorso configurato per '{key}' non esiste (sanitizzato): {path}")


validate_config(secrets)

# Esportazione costanti con fallback per i test
PATH_STORICO_DB = resolve_path(secrets.get("path_storico_db", ""))
PATH_GESTIONALE = resolve_path(secrets.get("path_gestionale", ""))
PATH_ATTIVITA_PROGRAMMATE = resolve_path(secrets.get("path_attivita_programmate", ""))

# --- GESTIONE DINAMICA GIORNALIERA ---
_raw_giornaliera = resolve_path(secrets.get("path_giornaliera_base", ""))
_current_year = datetime.date.today().year


def get_giornaliera_path(anno: int | None = None) -> str:
    """Restituisce il percorso della cartella giornaliere per l'anno specificato (default corrente)."""
    if not _raw_giornaliera:
        return ""

    path = Path(_raw_giornaliera)
    # Se il path punta già a una cartella "Giornaliere XXXX", risaliamo alla radice
    # Gestiamo sia separatori Windows che POSIX
    root = path.parent if "Giornaliere" in path.name else path

    target_year = anno if anno is not None else _current_year
    return str(root / f"Giornaliere {target_year}")


# La costante punterà sempre all'anno corrente per default
PATH_GIORNALIERA_BASE = get_giornaliera_path()

# --- SPREADSHEET & EMAIL ---
NOME_FOGLIO_RISPOSTE = secrets.get("nome_foglio_risposte", "Report Attività Giornaliera (Risposte)")
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

    return PATH_ATTIVITA_PROGRAMMATE


def get_storico_db_path() -> str:
    """Restituisce il percorso allo storico DB."""

    return PATH_STORICO_DB


def get_gestionale_path() -> str:
    """Restituisce il percorso al file gestionale."""

    return PATH_GESTIONALE


def check_data_connectivity() -> dict[str, bool]:
    """Verifica l'accessibilità dei percorsi dati critici."""
    return {
        "Database Tecnico (Excel)": Path(PATH_GIORNALIERA_BASE).exists(),
        "Storico DB": Path(PATH_STORICO_DB).exists(),
        "Attività Programmate": Path(PATH_ATTIVITA_PROGRAMMATE).exists(),
    }
