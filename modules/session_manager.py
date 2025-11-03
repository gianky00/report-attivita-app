import streamlit as st
import os
import json
import uuid
import datetime
import re

# --- GESTIONE SESSIONE ---
SESSION_DIR = "sessions"
SESSION_DURATION_HOURS = 8760 # 1 anno (365 * 24)
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

def save_session(matricola, role):
    """Salva i dati di una sessione in un file basato su token e restituisce il token."""
    token = str(uuid.uuid4())
    session_filepath = os.path.join(SESSION_DIR, f"session_{token}.json")
    session_data = {
        'authenticated_user': matricola,
        'ruolo': role,
        'timestamp': datetime.datetime.now().isoformat()
    }
    try:
        with open(session_filepath, 'w') as f:
            json.dump(session_data, f)
        return token
    except IOError as e:
        st.error(f"Impossibile salvare la sessione: {e}")
        return None

def load_session(token):
    """Carica una sessione da un file basato su token, se valida."""
    if not token or not re.match(r'^[a-f0-9-]+$', token):
        return False

    session_filepath = os.path.join(SESSION_DIR, f"session_{token}.json")
    if os.path.exists(session_filepath):
        try:
            with open(session_filepath, 'r') as f:
                session_data = json.load(f)

            session_time = datetime.datetime.fromisoformat(session_data['timestamp'])
            if datetime.datetime.now() - datetime.timedelta(hours=SESSION_DURATION_HOURS) < session_time:
                st.session_state.authenticated_user = session_data['authenticated_user']
                st.session_state.ruolo = session_data['ruolo']
                st.session_state.login_state = 'logged_in'
                return True
            else:
                delete_session(token) # Sessione scaduta
                return False
        except (IOError, json.JSONDecodeError, KeyError):
            delete_session(token) # File corrotto
            return False
    return False

def delete_session(token):
    """Cancella un file di sessione basato su token."""
    if not token:
        return
    session_filepath = os.path.join(SESSION_DIR, f"session_{token}.json")
    if os.path.exists(session_filepath):
        try:
            os.remove(session_filepath)
        except OSError:
            pass # Ignora errori
