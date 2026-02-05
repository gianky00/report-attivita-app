import datetime
import json
import re
import uuid
from contextlib import suppress
from pathlib import Path

import streamlit as st

# --- GESTIONE SESSIONE ---
from core.logging import get_logger

logger = get_logger(__name__)

SESSION_DIR = Path("sessions")
SESSION_DURATION_HOURS = 8760  # 1 anno (365 * 24)

# Crea la directory delle sessioni se non esiste
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def get_session_path(token: str) -> Path:
    """Restituisce il percorso del file di sessione per un dato token."""
    return SESSION_DIR / f"session_{token}.json"


def save_session(matricola, role):
    """Salva i dati di una sessione in un file basato su token e restituisce il token."""
    token = str(uuid.uuid4())
    session_filepath = get_session_path(token)
    session_data = {
        "authenticated_user": matricola,
        "ruolo": role,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    try:
        session_filepath.write_text(json.dumps(session_data), encoding="utf-8")
        return token
    except OSError as e:
        st.error(f"Impossibile salvare la sessione: {e}")
        return None


def load_session(token):
    """Carica una sessione da un file basato su token, se valida."""
    if not token or not re.match(r"^[a-f0-9-]+$", token):
        return False

    session_filepath = get_session_path(token)
    if session_filepath.exists():
        try:
            session_data = json.loads(session_filepath.read_text(encoding="utf-8"))

            session_time = datetime.datetime.fromisoformat(session_data["timestamp"])
            if (
                datetime.datetime.now()
                - datetime.timedelta(hours=SESSION_DURATION_HOURS)
                < session_time
            ):
                st.session_state.authenticated_user = session_data["authenticated_user"]
                st.session_state.ruolo = session_data["ruolo"]
                st.session_state.login_state = "logged_in"
                return True
            else:
                delete_session(token)  # Sessione scaduta
                return False
        except Exception:
            # Qualsiasi errore (JSON corrotto, chiavi mancanti, tipi errati, 
            # o problemi con st.session_state) porta alla distruzione della sessione.
            delete_session(token)
            return False
    return False


def delete_session(token):
    """Cancella un file di sessione basato su token."""
    if not token:
        return
    session_filepath = get_session_path(token)
    try:
        if session_filepath.exists():
            import gc
            import os
            gc.collect()  # Forza la chiusura di eventuali handle orfani
            os.remove(str(session_filepath))
            logger.debug(f"Sessione {token} rimossa con successo.")
    except Exception as e:
        logger.warning(f"Impossibile rimuovere la sessione {token}: {e}")
