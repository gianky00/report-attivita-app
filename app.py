import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import re
import os
import json
import uuid
import subprocess
import sys
from collections import defaultdict
import requests
import google.generativeai as genai
try:
    import win32com.client as win32
except ImportError:
    win32 = None
    pythoncom = None
import matplotlib.pyplot as plt
import threading
import learning_module
import bcrypt
import qrcode
import io
from modules.auth import (
    authenticate_user,
    generate_2fa_secret,
    get_provisioning_uri,
    verify_2fa_code,
    log_access_attempt,
    get_user_by_matricola,
    create_user,
    update_user
)
from modules.data_manager import (
    carica_knowledge_core,
    scrivi_o_aggiorna_risposta,
    trova_attivita,
    _carica_giornaliera_mese
)
from modules.db_manager import (
    get_shifts_by_type, get_reports_to_validate, delete_reports_by_ids,
    process_and_commit_validated_reports, salva_relazione,
    get_unvalidated_relazioni, process_and_commit_validated_relazioni, get_all_users,
    get_validated_intervention_reports, get_table_names, get_table_data, save_table_data,
    get_report_by_id, delete_report_by_id, insert_report, move_report_atomically,
    get_last_login, count_unread_notifications
)
from learning_module import load_report_knowledge_base, get_report_knowledge_base_count
from modules.oncall_logic import get_next_on_call_week
from modules.shift_management import (
    sync_oncall_shifts,
    log_shift_change,
    prenota_turno_logic,
    cancella_prenotazione_logic,
    richiedi_sostituzione_logic,
    rispondi_sostituzione_logic,
    pubblica_turno_in_bacheca_logic,
    prendi_turno_da_bacheca_logic
)
from modules.notifications import (
    leggi_notifiche,
    crea_notifica,
    segna_notifica_letta
)
from modules.email_sender import invia_email_con_outlook_async


# --- FUNZIONI DI SUPPORTO E CARICAMENTO DATI ---
@st.cache_resource
def autorizza_google():
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        if creds.access_token_expired:
            client.login()
        return client
    except FileNotFoundError:
        st.error("File 'credentials.json' non trovato. L'integrazione con Google Sheets è disabilitata.")
        return None

from modules.instrumentation_logic import find_and_analyze_tags, get_technical_suggestions, analyze_domain_terminology

@st.cache_data
def to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False).encode('utf-8')

# La funzione calculate_technician_performance è stata rimossa perché
# la logica è stata spostata in modules/db_manager.py per efficienza.
# La nuova funzione get_technician_performance_data esegue i calcoli
# direttamente nel database, riducendo drasticamente il carico sulla memoria
# e il tempo di elaborazione.


from components.ui_components import (
    visualizza_storico_organizzato,
    disegna_sezione_attivita,
    render_notification_center
)
from components.form_handlers import (
    to_csv,
    render_debriefing_ui,
    render_edit_shift_form
)
from pages.gestione_turni import (
    render_turni_list,
    render_reperibilita_tab,
    render_gestione_turni_tab
)
from pages.richieste import render_richieste_tab
from pages.admin import (
    render_caposquadra_view,
    render_sistema_view,
    render_gestione_account,
    render_technician_detail_view,
    render_report_validation_tab,
    render_access_logs_tab
)
from pages.guida import render_guida_tab
from modules.session_manager import (
    initialize_session_state,
    load_session,
    save_session,
    delete_session,
)
from pages.main_page import main_app


# --- GESTIONE LOGIN ---

initialize_session_state()

# --- Logica di avvio e caricamento sessione ---
# Se l'utente non è già loggato in st.session_state, prova a caricarlo dal token nell'URL
if not st.session_state.get('authenticated_user'):
    token = st.query_params.get("session_token")
    if token:
        if load_session(token):
            st.session_state.session_token = token # Mantieni il token in stato
        else:
            # Se il token non è valido, pulisci i query params per evitare loop
            st.query_params.clear()


# --- UI LOGIC ---

if st.session_state.login_state == 'logged_in':
    main_app(st.session_state.authenticated_user, st.session_state.ruolo)

else:
    st.set_page_config(layout="centered", page_title="Login")
    st.title("Accesso Area Gestionale")

    if st.session_state.login_state == 'password':
        with st.form("login_form"):
            matricola_inserita = st.text_input("Matricola")
            password_inserita = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Accedi")

            if submitted:
                if not matricola_inserita or not password_inserita:
                    st.warning("Per favore, inserisci Matricola e Password.")
                else:
                    status, user_data = authenticate_user(matricola_inserita, password_inserita)

                    if status == "2FA_REQUIRED":
                        log_access_attempt(matricola_inserita, "Password corretta, 2FA richiesta")
                        st.session_state.login_state = 'verify_2fa'
                        st.session_state.temp_user_for_2fa = matricola_inserita
                        st.rerun()
                    elif status == "2FA_SETUP_REQUIRED":
                        log_access_attempt(matricola_inserita, "Password corretta, setup 2FA richiesto")
                        st.session_state.login_state = 'setup_2fa'
                        _, st.session_state.ruolo = user_data
                        st.session_state.temp_user_for_2fa = matricola_inserita
                        st.rerun()
                    elif status == "FIRST_LOGIN_SETUP":
                        nome_completo, ruolo, password_fornita = user_data
                        hashed_password = bcrypt.hashpw(password_fornita.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                        user_info = get_user_by_matricola(matricola_inserita)
                        if not user_info: # First user ever
                            new_user_data = {
                                'Matricola': str(matricola_inserita), 'Nome Cognome': nome_completo,
                                'Ruolo': ruolo, 'PasswordHash': hashed_password,
                                'Link Attività': '', '2FA_Secret': None
                            }
                            create_user(new_user_data)
                        else: # Existing user, first login
                            update_user(matricola_inserita, {'PasswordHash': hashed_password})

                        st.success("Password creata con successo! Ora configura la sicurezza.")
                        log_access_attempt(matricola_inserita, "Primo login: Password creata")
                        st.session_state.login_state = 'setup_2fa'
                        st.session_state.temp_user_for_2fa = matricola_inserita
                        st.session_state.ruolo = ruolo
                        st.rerun()
                    else: # FAILED
                        log_access_attempt(matricola_inserita, "Credenziali non valide")
                        st.error("Credenziali non valide.")

    elif st.session_state.login_state == 'setup_2fa':
        st.subheader("Configurazione Sicurezza Account (2FA)")
        # ... (il resto della logica 2FA rimane quasi invariata, ma usa le nuove funzioni)
        matricola_to_setup = st.session_state.temp_user_for_2fa
        user_info = get_user_by_matricola(matricola_to_setup)
        user_name_for_display = user_info['Nome Cognome'] if user_info else "Utente"

        if not st.session_state.get('2fa_secret'):
            st.session_state['2fa_secret'] = generate_2fa_secret()
        secret = st.session_state['2fa_secret']

        uri = get_provisioning_uri(user_name_for_display, secret)
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_bytes = buf.getvalue()
        st.image(qr_bytes)
        st.code(secret)

        with st.form("verify_2fa_setup"):
            code = st.text_input("Inserisci il codice a 6 cifre per verificare")
            submitted = st.form_submit_button("Verifica e Attiva")
            if submitted:
                if verify_2fa_code(secret, code):
                    if update_user(matricola_to_setup, {'2FA_Secret': secret}):
                        log_access_attempt(matricola_to_setup, "Setup 2FA completato e login riuscito")
                        st.success("Configurazione 2FA completata! Accesso in corso...")
                        token = save_session(matricola_to_setup, st.session_state.ruolo)
                        st.session_state.login_state = 'logged_in'
                        st.session_state.authenticated_user = matricola_to_setup
                        st.session_state.session_token = token
                        st.query_params['session_token'] = token
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio della configurazione.")
                else:
                    log_access_attempt(matricola_to_setup, "Setup 2FA fallito (codice non valido)")
                    st.error("Codice non valido.")

    elif st.session_state.login_state == 'verify_2fa':
        st.subheader("Verifica in Due Passaggi")
        matricola_to_verify = st.session_state.temp_user_for_2fa
        user_row = get_user_by_matricola(matricola_to_verify)

        if not user_row or not user_row.get('2FA_Secret'):
            st.error("Errore di configurazione 2FA. Contatta un amministratore.")
            st.stop()

        secret = user_row['2FA_Secret']
        ruolo = user_row['Ruolo']
        nome_utente = user_row['Nome Cognome']

        with st.form("verify_2fa_login"):
            code = st.text_input(f"Ciao {nome_utente.split()[0]}, inserisci il codice di autenticazione")
            submitted = st.form_submit_button("Verifica")
            if submitted:
                if verify_2fa_code(secret, code):
                    log_access_attempt(matricola_to_verify, "Login 2FA riuscito")
                    st.success("Codice corretto! Accesso in corso...")
                    token = save_session(matricola_to_verify, ruolo)
                    st.session_state.login_state = 'logged_in'
                    st.session_state.authenticated_user = matricola_to_verify
                    st.session_state.ruolo = ruolo
                    st.session_state.session_token = token
                    st.query_params['session_token'] = token
                    st.rerun()
                else:
                    log_access_attempt(matricola_to_verify, "Login 2FA fallito (codice non valido)")
                    st.error("Codice non valido.")