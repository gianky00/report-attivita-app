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
    log_access_attempt
)
from modules.data_manager import (
    carica_knowledge_core,
    carica_gestionale,
    salva_gestionale_async,
    scrivi_o_aggiorna_risposta,
    trova_attivita
)
from modules.db_manager import (
    get_shifts_by_type, get_reports_to_validate, delete_reports_by_ids,
    process_and_commit_validated_reports, salva_relazione,
    get_unvalidated_relazioni, process_and_commit_validated_relazioni,
    get_validated_intervention_reports, get_table_names, get_table_data, save_table_data,
    get_report_by_id, delete_report_by_id, insert_report, move_report_atomically
)
from learning_module import load_report_knowledge_base, get_report_knowledge_base_count
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
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    if creds.access_token_expired:
        client.login()
    return client

from modules.instrumentation_logic import find_and_analyze_tags, get_technical_suggestions, analyze_domain_terminology

def revisiona_relazione_con_ia(_testo_originale, _knowledge_base):
    """
    Usa l'IA per revisionare una relazione tecnica, arricchendo la richiesta
    con analisi semantica della strumentazione basata su standard ISA S5.1.
    """
    # Funzione mantenuta per la revisione delle relazioni, ma non più per i report
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return {"error": "La chiave API di Gemini non è configurata."}
    if not _testo_originale.strip():
        return {"info": "Il testo della relazione è vuoto."}

    # 1. Analisi semantica della strumentazione e della terminologia
    loops, analyzed_tags = find_and_analyze_tags(_testo_originale)
    domain_terms = analyze_domain_terminology(_testo_originale)

    technical_summary = ""
    if loops:
        technical_summary += "Analisi del Contesto Strumentale:\n"
        for loop_id, components in loops.items():
            main_variable = components[0]['variable']
            technical_summary += f"- Loop di Controllo {loop_id} ({main_variable}):\n"
            for comp in components:
                technical_summary += f"  - {comp['tag']}: È un {comp['type']} ({comp['description']}).\n"

            controller = next((c for c in components if c['type'] == '[CONTROLLORE]'), None)
            actuator = next((c for c in components if c['type'] == '[ATUTTATORE]'), None)
            if controller and actuator:
                technical_summary += f"  - Relazione: Il controllore {controller['tag']} comanda l'attuatore {actuator['tag']}.\n"
        technical_summary += "\n"

    if domain_terms:
        technical_summary += "Terminologia Specifica Rilevata:\n"
        for term, definition in domain_terms.items():
            technical_summary += f"- {term.upper()}: {definition}.\n"
        technical_summary += "\n"

    # 2. Costruzione del prompt per l'IA
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-flash-latest')

        if technical_summary:
            prompt = f"""
            Sei un Direttore Tecnico di Manutenzione con profonda conoscenza della strumentazione (standard ISA S5.1) e della terminologia di impianto. Il tuo compito è riformulare la seguente relazione scritta da un tecnico, trasformandola in un report professionale, chiaro e tecnicamente consapevole.
            **INFORMAZIONI TECNICHE E TERMINOLOGICHE DA USARE (Know-How):**
            ---
            {technical_summary}
            ---
            Usa queste informazioni per interpretare correttamente le sigle (es. CTG, FCV301) e le relazioni tra i componenti. Riformula il testo per riflettere questa comprensione approfondita.
            **RELAZIONE ORIGINALE DA RIFORMULARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE RIFORMULATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """
        else:
            prompt = f"""
            Sei un revisore esperto di relazioni tecniche in ambito industriale. Il tuo compito è revisionare e migliorare il seguente testo scritto da un tecnico, mantenendo un tono professionale, chiaro e conciso. Correggi eventuali errori grammaticali o di battitura.
            **RELAZIONE DA REVISIONARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE REVISIONATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """

        response = model.generate_content(prompt)
        return {"success": True, "text": response.text}
    except Exception as e:
        return {"error": f"Errore durante la revisione IA: {str(e)}"}


@st.cache_data
def to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False).encode('utf-8')

# La funzione calculate_technician_performance è stata rimossa perché
# la logica è stata spostata in modules/db_manager.py per efficienza.
# La nuova funzione get_technician_performance_data esegue i calcoli
# direttamente nel database, riducendo drasticamente il carico sulla memoria
# e il tempo di elaborazione.

from components.menu import render_sidebar
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
from components.gestione_turni import (
    render_turni_list,
    render_reperibilita_tab
)
from components.richieste import render_richieste_tab
from components.admin import (
    render_admin_dashboard,
    render_gestione_account,
    render_technician_detail_view,
    render_report_validation_tab,
    render_access_logs_tab
)
from components.guida import render_guida_tab


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


# --- APPLICAZIONE STREAMLIT PRINCIPALE ---
def recupera_attivita_non_rendicontate(matricola_utente, df_contatti):
    """
    Recupera le attività non rendicontate degli ultimi 30 giorni.
    """
    oggi = datetime.date.today()
    attivita_da_recuperare = []
    for i in range(1, 31):
        giorno_controllo = oggi - datetime.timedelta(days=i)
        attivita_giorno = trova_attivita(matricola_utente, giorno_controllo.day, giorno_controllo.month, giorno_controllo.year, df_contatti)
        attivita_da_recuperare.extend(attivita_giorno)
    return attivita_da_recuperare

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def main_app(matricola_utente, ruolo):
    st.set_page_config(layout="wide", page_title="Gestionale")
    load_css('styles/style.css')

    if 'sidebar_state' not in st.session_state:
        st.session_state.sidebar_state = 'expanded'

    gestionale_data = carica_gestionale()
    df_contatti = gestionale_data['contatti']
    # Assicura che la matricola sia sempre una stringa per evitare errori di lookup
    df_contatti['Matricola'] = df_contatti['Matricola'].astype(str)

    # Ottieni il nome utente dalla matricola
    user_info = df_contatti[df_contatti['Matricola'] == str(matricola_utente)]
    if not user_info.empty:
        nome_utente_autenticato = user_info.iloc[0]['Nome Cognome']
    else:
        st.error("Errore critico: impossibile trovare i dati dell'utente loggato.")
        st.stop()


    # Sincronizza automaticamente i turni di reperibilità all'avvio
    today = datetime.date.today()
    start_sync_date = today.replace(day=1)
    # Calcola una finestra di sincronizzazione di circa 2 mesi (mese corrente + prossimo)
    end_sync_date = (start_sync_date + datetime.timedelta(days=35)).replace(day=1) + datetime.timedelta(days=31)

    if sync_oncall_shifts(gestionale_data, start_date=start_sync_date, end_date=end_sync_date):
        # Se sono stati aggiunti nuovi turni, salva il file gestionale
        salva_gestionale_async(gestionale_data)
        st.toast("Calendario reperibilità sincronizzato.")

    with st.sidebar:
        selected_page = render_sidebar(ruolo)

    if st.session_state.get('editing_turno_id'):
        render_edit_shift_form(gestionale_data)
    elif st.session_state.get('debriefing_task'):
        knowledge_core = carica_knowledge_core()
        if knowledge_core:
            task_info = st.session_state.debriefing_task
            data_riferimento_attivita = task_info.get('data_attivita', datetime.date.today())
            render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento_attivita)
    else:
        # Header con titolo, notifiche e pulsante di logout
        st.markdown('<div class="header">', unsafe_allow_html=True)

        st.markdown('<div class="hamburger">☰</div>', unsafe_allow_html=True)

        col2, col3, col4 = st.columns([0.7, 0.15, 0.15])
        with col2:
            st.markdown(f'<div class="title">{selected_page}</div>', unsafe_allow_html=True)
        with col3:
            st.write("") # Spacer
            st.write("") # Spacer
            user_notifications = leggi_notifiche(gestionale_data, matricola_utente)
            render_notification_center(user_notifications, gestionale_data, matricola_utente)
        with col4:
            st.write("")
            st.write("")
            if st.button("Logout", type="secondary"):
                token_to_delete = st.session_state.get('session_token')
                delete_session(token_to_delete)

                # Pulisce completamente lo stato della sessione per un logout sicuro
                keys_to_clear = [k for k in st.session_state.keys()]
                for key in keys_to_clear:
                    del st.session_state[key]

                # Rimuove il token dall'URL
                st.query_params.clear()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="main sidebar-{st.session_state.sidebar_state}">', unsafe_allow_html=True)

        oggi = datetime.date.today()

        attivita_da_recuperare = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)

        st.divider()

        if selected_page == "Attività di Oggi":
            st.header(f"Attività del {oggi.strftime('%d/%m/%Y')}")
            lista_attivita_raw = trova_attivita(matricola_utente, oggi.day, oggi.month, oggi.year, gestionale_data['contatti'])

            # Applica la logica dei falsi positivi anche per le attività di oggi
            lista_attivita_filtrata = [
                task for task in lista_attivita_raw
                if not any(
                    pd.to_datetime(interv.get('Data_Riferimento'), dayfirst=True, errors='coerce').date() >= oggi
                    for interv in task.get('storico', []) if pd.notna(pd.to_datetime(interv.get('Data_Riferimento'), dayfirst=True, errors='coerce'))
                )
            ]
            disegna_sezione_attivita(lista_attivita_filtrata, "today", ruolo)

        elif selected_page == "Recupero Attività":
            st.header("Recupero Attività Non Rendicontate (Ultimi 30 Giorni)")
            disegna_sezione_attivita(attivita_da_recuperare, "yesterday", ruolo)

        elif selected_page == "Attività Validate":
            st.header("Elenco Attività Validate")
            report_validati_df = get_validated_intervention_reports(matricola_tecnico=str(matricola_utente))
            if report_validati_df.empty:
                st.info("Non hai ancora report validati.")
            else:
                for _, report in report_validati_df.iterrows():
                    with st.expander(f"PdL `{report['pdl']}` - Intervento del {pd.to_datetime(report['data_riferimento_attivita']).strftime('%d/%m/%Y')}"):
                        st.markdown(f"**Descrizione:** {report['descrizione_attivita']}")
                        st.markdown(f"**Compilato il:** {pd.to_datetime(report['data_compilazione']).strftime('%d/%m/%Y %H:%M')}")
                        st.info(f"**Testo del Report:**\n\n{report['testo_report']}")
                        st.caption(f"ID Report: {report['id_report']} | Validato il: {pd.to_datetime(report['timestamp_validazione']).strftime('%d/%m/%Y %H:%M')}")

        # Contenuto per la nuova scheda "Compila Relazione"
        elif selected_page == "Compila Relazione":
            st.header("Compila Relazione di Reperibilità")

            kb_count = get_report_knowledge_base_count()
            if kb_count > 0:
                st.caption(f"ℹ️ L'IA si basa su {kb_count} relazioni per la correzione.")
            else:
                st.caption("ℹ️ Base di conoscenza per l'IA non trovata o vuota.")

            if 'relazione_testo' not in st.session_state: st.session_state.relazione_testo = ""
            if 'relazione_partner' not in st.session_state: st.session_state.relazione_partner = None
            if 'relazione_revisionata' not in st.session_state: st.session_state.relazione_revisionata = ""
            if 'technical_suggestions' not in st.session_state: st.session_state.technical_suggestions = []

            contatti_df = gestionale_data.get('contatti', pd.DataFrame())
            lista_partner = contatti_df[contatti_df['Matricola'] != str(matricola_utente)]['Nome Cognome'].tolist()

            with st.form("form_relazione"):
                col_tech, col_partner = st.columns(2)
                with col_tech: st.text_input("Tecnico Compilatore", value=nome_utente_autenticato, disabled=True)
                with col_partner: partner_selezionato = st.selectbox("Seleziona Partner (opzionale)", options=["Nessuno"] + sorted(lista_partner), index=0)

                c1, c2, c3 = st.columns(3)
                data_intervento = c1.date_input("Data Intervento*", help="Questo campo è obbligatorio.")
                ora_inizio = c2.text_input("Ora Inizio")
                ora_fine = c3.text_input("Ora Fine")

                st.session_state.relazione_testo = st.text_area("Corpo della Relazione", height=250, key="relazione_text_area", value=st.session_state.get('relazione_testo', ''))

                b1, b2, b3 = st.columns(3)
                submit_ai_button = b1.form_submit_button("🤖 Correggi con IA")
                submit_suggestion_button = b2.form_submit_button("💡 Suggerimento Tecnico")
                submit_save_button = b3.form_submit_button("✅ Invia Relazione", type="primary")

            # Logica dopo la sottomissione del form, con formattazione corretta
            if submit_ai_button:
                testo_da_revisionare = st.session_state.get('relazione_text_area', '')
                st.session_state.relazione_testo = testo_da_revisionare
                if not testo_da_revisionare.strip():
                    st.warning("Per favore, scrivi il corpo della relazione prima di chiedere la correzione.")
                elif not data_intervento:
                    st.error("Il campo 'Data Intervento' è obbligatorio.")
                else:
                    with st.spinner("L'IA sta analizzando la relazione..."):
                        result = revisiona_relazione_con_ia(testo_da_revisionare, None)
                        if result.get("success"):
                            st.session_state.relazione_revisionata = result["text"]
                            st.success("Relazione corretta con successo!")
                        elif "error" in result:
                            st.error(f"**Errore IA:** {result['error']}")
                        else:
                            st.info(result.get("info", "Nessun suggerimento dall'IA."))

            if submit_suggestion_button:
                testo_per_suggerimenti = st.session_state.get('relazione_text_area', '')
                if testo_per_suggerimenti.strip():
                    with st.spinner("Cerco suggerimenti tecnici..."):
                        suggestions = get_technical_suggestions(testo_per_suggerimenti)
                        st.session_state.technical_suggestions = suggestions
                        if not suggestions:
                            st.toast("Nessun suggerimento specifico trovato per questo testo.")
                else:
                    st.warning("Scrivi qualcosa nella relazione per ricevere suggerimenti.")

            if submit_save_button:
                testo_da_inviare = st.session_state.get('relazione_text_area', '')
                if not data_intervento:
                    st.error("Il campo 'Data Intervento' è obbligatorio prima di inviare.")
                elif not testo_da_inviare.strip():
                    st.error("Il corpo della relazione non può essere vuoto prima di inviare.")
                else:
                    id_relazione = f"REL_{int(datetime.datetime.now().timestamp())}"
                    dati_nuova_relazione = {
                        "id_relazione": id_relazione,
                        "data_intervento": data_intervento.isoformat(),
                        "tecnico_compilatore": nome_utente_autenticato,
                        "partner": partner_selezionato if partner_selezionato != "Nessuno" else None,
                        "ora_inizio": ora_inizio,
                        "ora_fine": ora_fine,
                        "corpo_relazione": testo_da_inviare,
                        "stato": "Inviata",
                        "timestamp_invio": datetime.datetime.now().isoformat()
                    }

                    if salva_relazione(dati_nuova_relazione):
                        st.success("Relazione salvata e inviata con successo!")
                        partner_text = f" in coppia con {partner_selezionato}" if partner_selezionato != "Nessuno" else ""
                        titolo_email = f"Relazione di Reperibilità del {data_intervento.strftime('%d/%m/%Y')} - {nome_utente_autenticato}"
                        html_body = f"""
                        <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                        <h3>Relazione di Reperibilità</h3>
                        <p><strong>Data:</strong> {data_intervento.strftime('%d/%m/%Y')}</p>
                        <p><strong>Tecnico:</strong> {nome_utente_autenticato}{partner_text}</p>
                        <p><strong>Orario:</strong> Da {ora_inizio or 'N/D'} a {ora_fine or 'N/D'}</p>
                        <hr>
                        <h4>Testo della Relazione:</h4>
                        <p>{testo_da_inviare.replace('\n', '<br>')}</p>
                        <br><hr>
                        <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                        <p><strong>Gianky Allegretti</strong><br>Direttore Tecnico</p>
                        </body></html>
                        """
                        invia_email_con_outlook_async(titolo_email, html_body)
                        st.balloons()
                        # Svuota i campi dopo l'invio
                        st.session_state.relazione_testo = ""
                        st.session_state.relazione_revisionata = ""
                        st.session_state.technical_suggestions = []
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio della relazione nel database.")

            if st.session_state.get('relazione_revisionata'):
                st.subheader("Testo corretto dall'IA")
                st.info(st.session_state.relazione_revisionata)
                if st.button("📝 Usa Testo Corretto"):
                    st.session_state.relazione_testo = st.session_state.relazione_revisionata
                    st.session_state.relazione_revisionata = ""
                    st.rerun()

            if st.session_state.get('technical_suggestions'):
                st.subheader("💡 Suggerimenti Tecnici")
                for suggestion in st.session_state.get('technical_suggestions', []):
                    st.info(suggestion)

        elif selected_page == "Gestione Turni":
            st.subheader("Gestione Turni")
            turni_disponibili_tab, bacheca_tab, sostituzioni_tab = st.tabs(["📅 Turni", "📢 Bacheca", "🔄 Sostituzioni"])
            with turni_disponibili_tab:
                assistenza_tab, straordinario_tab, reperibilita_tab = st.tabs(["Turni Assistenza", "Turni Straordinario", "Turni Reperibilità"])
                with assistenza_tab:
                    df_assistenza = get_shifts_by_type('Assistenza')
                    render_turni_list(df_assistenza, gestionale_data, matricola_utente, ruolo, "assistenza")
                with straordinario_tab:
                    df_straordinario = get_shifts_by_type('Straordinario')
                    render_turni_list(df_straordinario, gestionale_data, matricola_utente, ruolo, "straordinario")
                with reperibilita_tab:
                    render_reperibilita_tab(gestionale_data, matricola_utente, ruolo)
            with bacheca_tab:
                st.subheader("Turni Liberi in Bacheca")
                df_bacheca = gestionale_data.get('bacheca', pd.DataFrame())
                turni_disponibili_bacheca = df_bacheca[df_bacheca['Stato'] == 'Disponibile'].sort_values(by='Timestamp_Pubblicazione', ascending=False)
                if turni_disponibili_bacheca.empty: st.info("Al momento non ci sono turni liberi in bacheca.")
                else:
                    df_turni = gestionale_data['turni']
                    matricola_to_name = pd.Series(gestionale_data['contatti']['Nome Cognome'].values, index=gestionale_data['contatti']['Matricola'].astype(str)).to_dict()
                    for _, bacheca_entry in turni_disponibili_bacheca.iterrows():
                        try:
                            turno_details = df_turni[df_turni['ID_Turno'] == bacheca_entry['ID_Turno']].iloc[0]
                            matricola_originale = str(bacheca_entry['Tecnico_Originale_Matricola'])
                            nome_originale = matricola_to_name.get(matricola_originale, f"Matricola {matricola_originale}")
                            with st.container(border=True):
                                st.markdown(f"**{turno_details['Descrizione']}** ({bacheca_entry['Ruolo_Originale']})")
                                st.caption(f"Data: {pd.to_datetime(turno_details['Data']).strftime('%d/%m/%Y')} | Orario: {turno_details['OrarioInizio']} - {turno_details['OrarioFine']}")
                                st.write(f"Pubblicato da: {nome_originale} il {pd.to_datetime(bacheca_entry['Timestamp_Pubblicazione']).strftime('%d/%m %H:%M')}")
                                ruolo_richiesto = bacheca_entry['Ruolo_Originale']
                                is_eligible = not (ruolo_richiesto == 'Tecnico' and ruolo == 'Aiutante')
                                if is_eligible:
                                    if st.button("Prendi questo turno", key=f"take_{bacheca_entry['ID_Bacheca']}"):
                                        if prendi_turno_da_bacheca_logic(gestionale_data, matricola_utente, ruolo, bacheca_entry['ID_Bacheca']): salva_gestionale_async(gestionale_data); st.rerun()
                                else: st.info("Non hai il ruolo richiesto per questo turno.")
                        except IndexError: st.warning(f"Dettagli non trovati per il turno ID {bacheca_entry['ID_Turno']}. Potrebbe essere stato rimosso.")
            with sostituzioni_tab:
                st.subheader("Richieste di Sostituzione")
                df_sostituzioni = gestionale_data['sostituzioni']
                matricola_to_name = pd.Series(gestionale_data['contatti']['Nome Cognome'].values, index=gestionale_data['contatti']['Matricola'].astype(str)).to_dict()
                st.markdown("#### 📥 Richieste Ricevute")
                richieste_ricevute = df_sostituzioni[df_sostituzioni['Ricevente_Matricola'] == str(matricola_utente)]
                if richieste_ricevute.empty: st.info("Nessuna richiesta di sostituzione ricevuta.")
                for _, richiesta in richieste_ricevute.iterrows():
                    with st.container(border=True):
                        richiedente_nome = matricola_to_name.get(str(richiesta['Richiedente_Matricola']), "Sconosciuto")
                        st.markdown(f"**{richiedente_nome}** ti ha chiesto un cambio per il turno **{richiesta['ID_Turno']}**.")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Accetta", key=f"acc_{richiesta['ID_Richiesta']}"):
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, True): salva_gestionale_async(gestionale_data); st.rerun()
                        with c2:
                            if st.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, False): salva_gestionale_async(gestionale_data); st.rerun()
                st.divider()
                st.markdown("#### 📤 Richieste Inviate")
                richieste_inviate = df_sostituzioni[df_sostituzioni['Richiedente_Matricola'] == str(matricola_utente)]
                if richieste_inviate.empty: st.info("Nessuna richiesta di sostituzione inviata.")
                for _, richiesta in richieste_inviate.iterrows():
                    ricevente_nome = matricola_to_name.get(str(richiesta['Ricevente_Matricola']), "Sconosciuto")
                    st.markdown(f"- Richiesta inviata a **{ricevente_nome}** per il turno **{richiesta['ID_Turno']}**.")

        elif selected_page == "Richieste":
            st.header("Richieste")
            richieste_tabs = st.tabs(["Materiali", "Assenze"])
            with richieste_tabs[0]:
                st.subheader("Richiesta Materiali")
                with st.form("form_richiesta_materiali", clear_on_submit=True):
                    dettagli_richiesta = st.text_area("Elenca qui i materiali necessari:", height=150)
                    submitted = st.form_submit_button("Invia Richiesta Materiali", type="primary")
                    if submitted:
                        if dettagli_richiesta.strip():
                            new_id = f"MAT_{int(datetime.datetime.now().timestamp())}"
                            df_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())
                            nuova_richiesta_data = {'ID_Richiesta': new_id, 'Richiedente_Matricola': str(matricola_utente), 'Timestamp': datetime.datetime.now(), 'Stato': 'Inviata', 'Dettagli': dettagli_richiesta}
                            if not df_materiali.columns.empty: nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data], columns=df_materiali.columns)
                            else: nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data])
                            gestionale_data['richieste_materiali'] = pd.concat([df_materiali, nuova_richiesta_df], ignore_index=True)
                            if salva_gestionale_async(gestionale_data):
                                st.success("Richiesta materiali inviata con successo!")
                                titolo_email = f"Nuova Richiesta Materiali da {nome_utente_autenticato}"
                                html_body = f"""
                                <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                                <h3>Nuova Richiesta Materiali</h3>
                                <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                                <p><strong>Data e Ora:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                                <hr>
                                <h4>Materiali Richiesti:</h4>
                                <p>{dettagli_richiesta.replace('\n', '<br>')}</p>
                                <br><hr>
                                <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                                <p><strong>Gianky Allegretti</strong><br>
                                Direttore Tecnico</p>
                                </body></html>
                                """
                                invia_email_con_outlook_async(titolo_email, html_body)
                                st.rerun()
                            else: st.error("Errore durante il salvataggio della richiesta.")
                        else: st.warning("Il campo dei materiali non può essere vuoto.")
                st.divider()
                st.subheader("Storico Richieste Materiali")
                df_richieste_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())
                if df_richieste_materiali.empty: st.info("Nessuna richiesta di materiali inviata.")
                else:
                    df_contatti = gestionale_data.get('contatti', pd.DataFrame())
                    df_richieste_con_nome = pd.merge(df_richieste_materiali, df_contatti[['Matricola', 'Nome Cognome']], left_on='Richiedente_Matricola', right_on='Matricola', how='left')
                    df_richieste_con_nome['Nome Cognome'] = df_richieste_con_nome['Nome Cognome'].fillna('Sconosciuto')
                    df_richieste_con_nome['Timestamp'] = pd.to_datetime(df_richieste_con_nome['Timestamp'])
                    display_cols = ['Timestamp', 'Nome Cognome', 'Dettagli', 'Stato']
                    final_cols = [col for col in display_cols if col in df_richieste_con_nome.columns]
                    st.dataframe(df_richieste_con_nome[final_cols].sort_values(by="Timestamp", ascending=False), width='stretch')

            with richieste_tabs[1]:
                st.subheader("Richiesta Assenze (Ferie/Permessi)")
                with st.form("form_richiesta_assenze", clear_on_submit=True):
                    tipo_assenza = st.selectbox("Tipo di Assenza", ["Ferie", "Permesso (L. 104)"])
                    col1, col2 = st.columns(2)
                    data_inizio = col1.date_input("Data Inizio")
                    data_fine = col2.date_input("Data Fine")
                    note_assenza = st.text_area("Note (opzionale):", height=100)
                    submitted_assenza = st.form_submit_button("Invia Richiesta Assenza", type="primary")
                    if submitted_assenza:
                        if data_inizio and data_fine:
                            if data_inizio > data_fine: st.error("La data di inizio non può essere successiva alla data di fine.")
                            else:
                                new_id = f"ASS_{int(datetime.datetime.now().timestamp())}"
                                nuova_richiesta_assenza = pd.DataFrame([{'ID_Richiesta': new_id, 'Richiedente_Matricola': str(matricola_utente), 'Timestamp': datetime.datetime.now(), 'Tipo_Assenza': tipo_assenza, 'Data_Inizio': pd.to_datetime(data_inizio), 'Data_Fine': pd.to_datetime(data_fine), 'Note': note_assenza, 'Stato': 'Inviata'}])
                                df_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
                                gestionale_data['richieste_assenze'] = pd.concat([df_assenze, nuova_richiesta_assenza], ignore_index=True)
                                if salva_gestionale_async(gestionale_data):
                                    st.success("Richiesta di assenza inviata con successo!")
                                    titolo_email = f"Nuova Richiesta di Assenza da {nome_utente_autenticato}"
                                    html_body = f"""
                                    <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                                    <h3>Nuova Richiesta di Assenza</h3>
                                    <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                                    <p><strong>Tipo:</strong> {tipo_assenza}</p>
                                    <p><strong>Periodo:</strong> dal {data_inizio.strftime('%d/%m/%Y')} al {data_fine.strftime('%d/%m/%Y')}</p>
                                    <hr>
                                    <h4>Note:</h4>
                                    <p>{note_assenza.replace('\n', '<br>') if note_assenza else 'Nessuna nota.'}</p>
                                    <br><hr>
                                    <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                                    <p><strong>Gianky Allegretti</strong><br>
                                    Direttore Tecnico</p>
                                    </body></html>
                                    """
                                    invia_email_con_outlook_async(titolo_email, html_body)
                                    st.rerun()
                                else: st.error("Errore durante il salvataggio della richiesta.")
                        else: st.warning("Le date di inizio e fine sono obbligatorie.")
                if ruolo == "Amministratore":
                    st.divider()
                    st.subheader("Storico Richieste Assenze (Visibile solo agli Admin)")
                    df_richieste_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
                    if df_richieste_assenze.empty: st.info("Nessuna richiesta di assenza inviata.")
                    else:
                        df_richieste_assenze['Timestamp'] = pd.to_datetime(df_richieste_assenze['Timestamp'])
                        df_richieste_assenze['Data_Inizio'] = pd.to_datetime(df_richieste_assenze['Data_Inizio']).dt.strftime('%d/%m/%Y')
                        df_richieste_assenze['Data_Fine'] = pd.to_datetime(df_richieste_assenze['Data_Fine']).dt.strftime('%d/%m/%Y')
                        st.dataframe(df_richieste_assenze.sort_values(by="Timestamp", ascending=False), width='stretch')

        elif selected_page == "Storico":
            from components.storico import render_storico_tab
            render_storico_tab()

        elif selected_page == "Guida":
            render_guida_tab(ruolo)

        elif selected_page == "Dashboard Caposquadra":
            st.subheader("Dashboard di Controllo")
            if st.session_state.get('detail_technician_matricola'): render_technician_detail_view()
            else:

                caposquadra_tabs = st.tabs(["Performance Team", "Crea Nuovo Turno", "Gestione Dati", "Validazione Report"])
                with caposquadra_tabs[0]:
                    st.markdown("#### Seleziona Intervallo Temporale")
                    if 'perf_start_date' not in st.session_state: st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30)
                    if 'perf_end_date' not in st.session_state: st.session_state.perf_end_date = datetime.date.today()
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                    if c1.button("Oggi"): st.session_state.perf_start_date = st.session_state.perf_end_date = datetime.date.today()
                    if c2.button("Ultimi 7 giorni"): st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=7); st.session_state.perf_end_date = datetime.date.today()
                    if c3.button("Ultimi 30 giorni"): st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30); st.session_state.perf_end_date = datetime.date.today()
                    col1, col2 = st.columns(2)
                    with col1: st.date_input("Data di Inizio", key="perf_start_date", format="DD/MM/YYYY")
                    with col2: st.date_input("Data di Fine", key="perf_end_date", format="DD/MM/YYYY")
                    st.info("La sezione di performance è in fase di Sviluppo.")
                with caposquadra_tabs[1]:
                    with st.form("new_shift_form", clear_on_submit=True):
                        st.subheader("Dettagli Nuovo Turno")
                        tipo_turno = st.selectbox("Tipo Turno", ["Assistenza", "Straordinario"])
                        desc_turno = st.text_input("Descrizione Turno (es. 'Mattina', 'Straordinario Sabato')")
                        data_turno = st.date_input("Data Turno")
                        col1, col2 = st.columns(2)
                        with col1: ora_inizio = st.time_input("Orario Inizio", datetime.time(8, 0))
                        with col2: ora_fine = st.time_input("Orario Fine", datetime.time(17, 0))
                        col3, col4 = st.columns(2)
                        with col3: posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1)
                        with col4: posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1)
                        if st.form_submit_button("Crea Turno"):
                            if not desc_turno: st.error("La descrizione non può essere vuota.")
                            else:
                                new_id = f"T_{int(datetime.datetime.now().timestamp())}"
                                nuovo_turno = pd.DataFrame([{'ID_Turno': new_id, 'Descrizione': desc_turno, 'Data': pd.to_datetime(data_turno), 'OrarioInizio': ora_inizio.strftime('%H:%M'), 'OrarioFine': ora_fine.strftime('%H:%M'), 'PostiTecnico': posti_tech, 'PostiAiutante': posti_aiut, 'Tipo': tipo_turno}])
                                gestionale_data['turni'] = pd.concat([gestionale_data['turni'], nuovo_turno], ignore_index=True)
                                df_contatti = gestionale_data.get('contatti')
                                if df_contatti is not None:
                                    utenti_da_notificare = df_contatti['Matricola'].tolist()
                                    messaggio = f"📢 Nuovo turno disponibile: '{desc_turno}' il {pd.to_datetime(data_turno).strftime('%d/%m/%Y')}."
                                    for matricola in utenti_da_notificare: crea_notifica(gestionale_data, matricola, messaggio)
                                if salva_gestionale_async(gestionale_data):
                                    st.success(f"Turno '{desc_turno}' creato con successo! Notifiche inviate.")
                                    st.rerun()
                                else: st.error("Errore nel salvataggio del nuovo turno.")
                with caposquadra_tabs[2]:
                    st.header("Gestione Dati Avanzata")

                    editor_tab, report_tab, sync_tab = st.tabs(["Editor Tabelle Database", "Gestione Report", "Sincronizzazione Manuale"])

                    with editor_tab:
                        st.subheader("Modifica Diretta Tabelle")
                        st.warning("ATTENZIONE: La modifica diretta dei dati può causare instabilità. Procedere con cautela.")

                        table_names = get_table_names()
                        if table_names:
                            selected_table = st.selectbox(
                                "Seleziona una tabella da modificare",
                                options=[""] + sorted(table_names),
                                key="db_editor_table_select"
                            )

                            if selected_table:
                                if st.session_state.get("current_table_for_editing") != selected_table:
                                    st.session_state.current_table_for_editing = selected_table
                                    with st.spinner(f"Caricamento dati da '{selected_table}'..."):
                                        df = get_table_data(selected_table)
                                        st.session_state.edited_df = df.copy()

                                if "edited_df" in st.session_state:
                                    st.markdown(f"### Modifica Tabella: `{selected_table}`")

                                    edited_df_from_editor = st.data_editor(
                                        st.session_state.edited_df,
                                        num_rows="dynamic",
                                        key=f"editor_{selected_table}",
                                        width='stretch'
                                    )

                                    if not st.session_state.edited_df.equals(edited_df_from_editor):
                                        st.session_state.edited_df = edited_df_from_editor
                                        st.rerun()

                                    if st.button("Salva Modifiche", key=f"save_{selected_table}", type="primary"):
                                        with st.spinner("Salvataggio in corso..."):
                                            if save_table_data(st.session_state.edited_df, selected_table):
                                                st.success(f"Tabella `{selected_table}` aggiornata con successo!")
                                                del st.session_state.current_table_for_editing
                                                del st.session_state.edited_df
                                                st.rerun()
                                            else:
                                                st.error("Errore durante il salvataggio dei dati.")
                        else:
                            st.error("Impossibile recuperare l'elenco delle tabelle dal database.")

                    with report_tab:
                        st.subheader("Gestione Ciclo di Vita dei Report")

                        st.text_input("Cerca Report per ID", key="report_id_search")

                        if st.session_state.report_id_search:
                            report_id = st.session_state.report_id_search.strip()
                            report_to_validate = get_report_by_id(report_id, "report_da_validare")
                            report_validated = get_report_by_id(report_id, "report_interventi")

                            if report_to_validate:
                                st.markdown(f"#### Dettagli Report `{report_id}`")
                                st.success("Stato: In Attesa di Validazione")
                                st.json(report_to_validate)

                                col1, col2 = st.columns(2)
                                if col1.button("Forza Validazione", key=f"force_validate_{report_id}", type="primary"):
                                    if move_report_atomically(report_to_validate, "report_da_validare", "report_interventi"):
                                        st.success(f"Report {report_id} spostato in 'report_interventi'.")
                                        st.session_state.report_id_search = "" # Clear search
                                        st.rerun()
                                    else:
                                        st.error("Errore durante lo spostamento del report.")

                                if col2.button("Cancella Definitivamente", key=f"delete_unvalidated_{report_id}"):
                                    if delete_report_by_id(report_id, "report_da_validare"):
                                        st.success(f"Report {report_id} cancellato da 'report_da_validare'.")
                                        st.session_state.report_id_search = ""
                                        st.rerun()
                                    else:
                                        st.error("Errore durante la cancellazione del report.")

                            elif report_validated:
                                st.markdown(f"#### Dettagli Report `{report_id}`")
                                st.info("Stato: Validato")
                                st.json(report_validated)

                                col1, col2 = st.columns(2)
                                if col1.button("Annulla Validazione", key=f"revert_validation_{report_id}"):
                                    if move_report_atomically(report_validated, "report_interventi", "report_da_validare"):
                                        st.success(f"Report {report_id} spostato nuovamente in 'report_da_validare'.")
                                        st.session_state.report_id_search = ""
                                        st.rerun()
                                    else:
                                        st.error("Errore durante lo spostamento del report.")

                                if col2.button("Cancella Definitivamente", key=f"delete_validated_{report_id}"):
                                    if delete_report_by_id(report_id, "report_interventi"):
                                        st.success(f"Report {report_id} cancellato da 'report_interventi'.")
                                        st.session_state.report_id_search = ""
                                        st.rerun()
                                    else:
                                        st.error("Errore durante la cancellazione del report.")

                            else:
                                st.warning(f"Nessun report trovato con ID `{report_id}` in nessuna delle tabelle di destinazione.")

                    with sync_tab:
                        st.subheader("Sincronizzazione Manuale DB-Excel")
                        st.info("Questa operazione avvia la macro `AggiornaRisposte` nel file `Database_Report_Attivita.xlsm` per sincronizzare i dati.")
                        if st.button("Avvia Sincronizzazione", type="primary"):
                            with st.spinner("Esecuzione della macro in corso... L'operazione potrebbe richiedere alcuni minuti."):
                                try:
                                    python_executable = sys.executable
                                    script_path = os.path.join(os.path.dirname(__file__), "run_excel_macro.py")
                                    result = subprocess.run(
                                        [python_executable, script_path],
                                        capture_output=True, text=True, check=True, encoding='utf-8'
                                    )
                                    st.success("Operazione completata con successo!")
                                    st.code(result.stdout)
                                except FileNotFoundError:
                                    st.error("Errore: Impossibile trovare lo script `run_excel_macro.py`.")
                                except subprocess.CalledProcessError as e:
                                    st.error("Errore durante l'esecuzione dello script di sincronizzazione:")
                                    st.code(e.stderr)
                                except Exception as e:
                                    st.error(f"Si è verificato un errore imprevisto: {e}")

                with caposquadra_tabs[3]:
                    validation_tabs = st.tabs(["Validazione Report Attività", "Validazione Relazioni"])
                    with validation_tabs[0]:
                        render_report_validation_tab(matricola_utente)
                    with validation_tabs[1]:
                        st.subheader("Validazione Relazioni Inviate")
                        unvalidated_relazioni_df = get_unvalidated_relazioni()

                        if unvalidated_relazioni_df.empty:
                            st.success("🎉 Nessuna nuova relazione da validare al momento.")
                        else:
                            st.info(f"Ci sono {len(unvalidated_relazioni_df)} relazioni da validare.")

                            # Convert date columns for better display in data_editor
                            if 'data_intervento' in unvalidated_relazioni_df.columns:
                                unvalidated_relazioni_df['data_intervento'] = pd.to_datetime(unvalidated_relazioni_df['data_intervento'], errors='coerce').dt.strftime('%d/%m/%Y')
                            if 'timestamp_invio' in unvalidated_relazioni_df.columns:
                                unvalidated_relazioni_df['timestamp_invio'] = pd.to_datetime(unvalidated_relazioni_df['timestamp_invio'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')


                            edited_relazioni_df = st.data_editor(
                                unvalidated_relazioni_df,
                                num_rows="dynamic",
                                key="relazioni_editor",
                                width='stretch',
                                column_config={
                                    "corpo_relazione": st.column_config.TextColumn(width="large"),
                                    "id_relazione": st.column_config.Column(disabled=True),
                                    "timestamp_invio": st.column_config.Column(disabled=True),
                                }
                            )

                            if st.button("✅ Salva Relazioni Validate", type="primary"):
                                with st.spinner("Salvataggio delle relazioni in corso..."):
                                    if process_and_commit_validated_relazioni(edited_relazioni_df, matricola_utente):
                                        st.success("Relazioni validate e salvate con successo!")
                                        st.rerun()
                                    else:
                                        st.error("Si è verificato un errore durante il salvataggio delle relazioni.")

        elif selected_page == "Dashboard Tecnica":
            tecnica_tabs = st.tabs(["Gestione Account", "Cronologia Accessi", "Gestione IA"])
            with tecnica_tabs[0]: render_gestione_account(gestionale_data)
            with tecnica_tabs[1]:
                st.subheader("Cronologia Accessi")
                access_logs_df = gestionale_data.get('access_logs', pd.DataFrame())
                if access_logs_df.empty:
                    st.info("Nessun log di accesso registrato.")
                else:
                    st.dataframe(access_logs_df.sort_values(by="timestamp", ascending=False), width='stretch')
            with tecnica_tabs[2]:
                st.header("Gestione Intelligenza Artificiale")
                ia_sub_tabs = st.tabs(["Revisione Conoscenze", "Memoria IA"])
                with ia_sub_tabs[0]:
                    st.markdown("### 🧠 Revisione Voci del Knowledge Core")
                    unreviewed_entries = learning_module.load_unreviewed_knowledge()
                    pending_entries = [e for e in unreviewed_entries if e.get('stato') == 'in attesa di revisione']
                    if not pending_entries: st.success("🎉 Nessuna nuova voce da revisionare!")
                    else: st.info(f"Ci sono {len(pending_entries)} nuove voci suggerite dai tecnici da revisionare.")
                    for i, entry in enumerate(pending_entries):
                        with st.expander(f"**Voce ID:** `{entry['id']}` - **Attività:** {entry['attivita_collegata']}", expanded=i==0):
                            st.markdown(f"*Suggerito da: **{entry['suggerito_da']}** il {datetime.datetime.fromisoformat(entry['data_suggerimento']).strftime('%d/%m/%Y %H:%M')}*")
                            st.markdown(f"*PdL di riferimento: `{entry['pdl']}`*")
                            st.write("**Dettagli del report compilato:**"); st.json(entry['dettagli_report'])
                            st.markdown("---"); st.markdown("**Azione di Integrazione**")
                            col1, col2 = st.columns(2)
                            with col1:
                                new_equipment_key = st.text_input("Nuova Chiave Attrezzatura (es. 'motore_elettrico')", key=f"key_{entry['id']}")
                                new_display_name = st.text_input("Nome Visualizzato (es. 'Motore Elettrico')", key=f"disp_{entry['id']}")
                            with col2:
                                if st.button("✅ Integra nel Knowledge Core", key=f"integrate_{entry['id']}", type="primary"):
                                    if new_equipment_key and new_display_name:
                                        first_question = {"id": "sintomo_iniziale", "text": "Qual era il sintomo principale?", "options": {k.lower().replace(' ', '_'): v for k, v in entry['dettagli_report'].items()}}
                                        details = {"equipment_key": new_equipment_key, "display_name": new_display_name, "new_question": first_question}
                                        result = learning_module.integrate_knowledge(entry['id'], details)
                                        if result.get("success"): st.success(f"Voce '{entry['id']}' integrata con successo!"); st.cache_data.clear(); st.rerun()
                                        else: st.error(f"Errore integrazione: {result.get('error')}")
                                    else: st.warning("Per integrare, fornisci sia la chiave che il nome visualizzato.")
                with ia_sub_tabs[1]:
                    st.subheader("Gestione Modello IA")
                    st.info("Usa questo pulsante per aggiornare la base di conoscenza dell'IA con le nuove relazioni inviate. L'operazione potrebbe richiedere alcuni minuti.")
                    if st.button("🧠 Aggiorna Memoria IA", type="primary"):
                        with st.spinner("Ricostruzione dell'indice in corso..."):
                            result = learning_module.build_knowledge_base()
                        if result.get("success"): st.success(result.get("message")); st.cache_data.clear()
                        else: st.error(result.get("message"))
        st.markdown('</div>', unsafe_allow_html=True)

# --- GESTIONE LOGIN ---

# Initialize session state keys if they don't exist
keys_to_initialize = {
    'login_state': 'password', # 'password', 'setup_2fa', 'verify_2fa', 'logged_in'
    'authenticated_user': None, # Ora conterrà la MATRICOLA
    'ruolo': None,
    'debriefing_task': None,
    'temp_user_for_2fa': None, # Ora conterrà la MATRICOLA
    '2fa_secret': None,
    'completed_tasks_yesterday': []
}
for key, default_value in keys_to_initialize.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

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
    
    gestionale = carica_gestionale()
    if not gestionale or 'contatti' not in gestionale:
        st.error("Errore critico: impossibile caricare i dati degli utenti.")
        st.stop()

    df_contatti = gestionale['contatti']
    # Assicura che la matricola sia una stringa per tutta la logica di login/2FA
    df_contatti['Matricola'] = df_contatti['Matricola'].astype(str)

    if st.session_state.login_state == 'password':
        with st.form("login_form"):
            matricola_inserita = st.text_input("Matricola")
            password_inserita = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Accedi")

            if submitted:
                if not matricola_inserita or not password_inserita:
                    st.warning("Per favore, inserisci Matricola e Password.")
                else:
                    status, user_data = authenticate_user(matricola_inserita, password_inserita, df_contatti)

                    # user_data ora contiene il nome_completo, non la matricola.
                    # Usiamo la matricola_inserita, che è stata validata, per il session_state.
                    if status == "2FA_REQUIRED":
                        log_access_attempt(gestionale, matricola_inserita, "Password corretta, 2FA richiesta")
                        salva_gestionale_async(gestionale)
                        st.session_state.login_state = 'verify_2fa'
                        st.session_state.temp_user_for_2fa = matricola_inserita # Salva la matricola
                        st.rerun()
                    elif status == "2FA_SETUP_REQUIRED":
                        log_access_attempt(gestionale, matricola_inserita, "Password corretta, setup 2FA richiesto")
                        salva_gestionale_async(gestionale)
                        st.session_state.login_state = 'setup_2fa'
                        _, st.session_state.ruolo = user_data # user_data è (nome_completo, ruolo)
                        st.session_state.temp_user_for_2fa = matricola_inserita # Salva la matricola
                        st.rerun()

                    elif status == "FIRST_LOGIN_SETUP":
                        nome_completo, ruolo, password_fornita = user_data
                        hashed_password = bcrypt.hashpw(password_fornita.encode('utf-8'), bcrypt.gensalt())

                        # Se il dataframe contatti è vuoto, questo è il primo utente in assoluto.
                        if df_contatti.empty:
                            new_user_data = {
                                'Matricola': str(matricola_inserita),
                                'Nome Cognome': nome_completo,
                                'Ruolo': ruolo,
                                'PasswordHash': hashed_password.decode('utf-8'),
                                'Link Attività': '',
                                '2FA_Secret': None
                            }
                            new_user_df = pd.DataFrame([new_user_data])
                            gestionale['contatti'] = pd.concat([df_contatti, new_user_df], ignore_index=True)
                        else:
                            # Altrimenti, è un utente esistente che sta impostando la password per la prima volta.
                            user_idx = df_contatti.index[df_contatti['Matricola'] == str(matricola_inserita)][0]
                            df_contatti.loc[user_idx, 'PasswordHash'] = hashed_password.decode('utf-8')

                        # Salvataggio nel database
                        if salva_gestionale_async(gestionale):
                            st.success("Password creata con successo! Ora configura la sicurezza.")
                            log_access_attempt(gestionale, matricola_inserita, "Primo login: Password creata")
                            salva_gestionale_async(gestionale) # Salva anche il log

                            # Procedi al setup della 2FA
                            st.session_state.login_state = 'setup_2fa'
                            st.session_state.temp_user_for_2fa = matricola_inserita
                            st.session_state.ruolo = ruolo
                            st.rerun()
                        else:
                            st.error("Errore critico: impossibile salvare la nuova password.")

                    else: # FAILED
                        log_access_attempt(gestionale, matricola_inserita, "Credenziali non valide")
                        salva_gestionale_async(gestionale)
                        st.error("Credenziali non valide.")

    elif st.session_state.login_state == 'setup_2fa':
        st.subheader("Configurazione Sicurezza Account (2FA)")
        st.info("Per una maggiore sicurezza, è necessario configurare la verifica in due passaggi.")

        if not st.session_state.get('2fa_secret'):
            st.session_state['2fa_secret'] = generate_2fa_secret()

        secret = st.session_state['2fa_secret']
        matricola_to_setup = st.session_state['temp_user_for_2fa']

        # Recupera il nome utente per la visualizzazione
        user_name_for_display = df_contatti[df_contatti['Matricola'] == str(matricola_to_setup)].iloc[0]['Nome Cognome']

        uri = get_provisioning_uri(user_name_for_display, secret)
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_bytes = buf.getvalue()

        st.image(qr_bytes)
        st.markdown("1. Installa un'app di autenticazione (es. Google Authenticator, Microsoft Authenticator).")
        st.markdown("2. Scansiona questo QR Code con l'app.")
        st.markdown("3. Se non puoi scansionare, inserisci manualmente la seguente chiave:")
        st.code(secret)

        with st.form("verify_2fa_setup"):
            code = st.text_input("Inserisci il codice a 6 cifre mostrato dall'app per verificare")
            submitted = st.form_submit_button("Verifica e Attiva")

            if submitted:
                if verify_2fa_code(secret, code):
                    # Salva il segreto nel file gestionale
                    user_idx = df_contatti[df_contatti['Matricola'] == str(matricola_to_setup)].index[0]
                    if '2FA_Secret' not in df_contatti.columns:
                        df_contatti['2FA_Secret'] = None
                    df_contatti.loc[user_idx, '2FA_Secret'] = secret

                    if salva_gestionale_async(gestionale):
                        log_access_attempt(gestionale, matricola_to_setup, "Setup 2FA completato e login riuscito")
                        salva_gestionale_async(gestionale) # Salva anche il log
                        st.success("Configurazione 2FA completata con successo! Accesso in corso...")
                        token = save_session(matricola_to_setup, st.session_state.ruolo)
                        if token:
                            st.session_state.login_state = 'logged_in'
                            st.session_state.authenticated_user = matricola_to_setup
                            st.session_state.session_token = token
                            st.query_params['session_token'] = token
                            st.rerun()
                        else:
                            st.error("Impossibile creare una sessione dopo la configurazione 2FA.")
                    else:
                        st.error("Errore durante il salvataggio della configurazione. Riprova.")
                else:
                    log_access_attempt(gestionale, matricola_to_setup, "Setup 2FA fallito (codice non valido)")
                    salva_gestionale_async(gestionale)
                    st.error("Codice non valido. Riprova.")

    elif st.session_state.login_state == 'verify_2fa':
        st.subheader("Verifica in Due Passaggi")
        matricola_to_verify = st.session_state.temp_user_for_2fa
        user_row = df_contatti[df_contatti['Matricola'] == str(matricola_to_verify)].iloc[0]
        secret = user_row['2FA_Secret']
        ruolo = user_row['Ruolo']
        nome_utente = user_row['Nome Cognome']

        with st.form("verify_2fa_login"):
            code = st.text_input(f"Ciao {nome_utente.split()[0]}, inserisci il codice dalla tua app di autenticazione")
            submitted = st.form_submit_button("Verifica")

            if submitted:
                if verify_2fa_code(secret, code):
                    log_access_attempt(gestionale, matricola_to_verify, "Login 2FA riuscito")
                    salva_gestionale_async(gestionale)
                    st.success("Codice corretto! Accesso in corso...")
                    token = save_session(matricola_to_verify, ruolo)
                    if token:
                        st.session_state.login_state = 'logged_in'
                        st.session_state.authenticated_user = matricola_to_verify
                        st.session_state.ruolo = ruolo
                        st.session_state.session_token = token
                        st.query_params['session_token'] = token
                        st.rerun()
                    else:
                        st.error("Impossibile creare una sessione dopo la verifica 2FA.")
                else:
                    log_access_attempt(gestionale, matricola_to_verify, "Login 2FA fallito (codice non valido)")
                    salva_gestionale_async(gestionale)
                    st.error("Codice non valido. Riprova.")
