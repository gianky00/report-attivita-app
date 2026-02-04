import datetime
import json
import re
import uuid
from contextlib import suppress
from pathlib import Path

import streamlit as st

# --- GESTIONE SESSIONE ---
SESSION_DIR = Path("sessions")
SESSION_DURATION_HOURS = 8760  # 1 anno (365 * 24)

# Crea la directory delle sessioni se non esiste
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(matricola, role):
    """Salva i dati di una sessione in un file basato su token e restituisce il token."""
    token = str(uuid.uuid4())
    session_filepath = SESSION_DIR / f"session_{token}.json"
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

    session_filepath = SESSION_DIR / f"session_{token}.json"
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
        except (OSError, json.JSONDecodeError, KeyError):
            delete_session(token)  # File corrotto
            return False
    return False


def delete_session(token):
    """Cancella un file di sessione basato su token."""
    if not token:
        return
    session_filepath = SESSION_DIR / f"session_{token}.json"
    with suppress(OSError):
        session_filepath.unlink(missing_ok=True)
