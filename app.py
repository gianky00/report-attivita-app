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
    trova_attivita
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
    render_reperibilita_tab
)
from pages.richieste import render_richieste_tab
from pages.admin import (
    render_admin_dashboard,
    render_gestione_account,
    render_technician_detail_view,
    render_report_validation_tab,
    render_access_logs_tab
)
from pages.guida import render_guida_tab


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
        for task in attivita_giorno:
            task['data_attivita'] = giorno_controllo
        attivita_da_recuperare.extend(attivita_giorno)
    return attivita_da_recuperare

def main_app(matricola_utente, ruolo):
    st.set_page_config(layout="wide", page_title="Gestionale", initial_sidebar_state="collapsed")

    def load_css(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    load_css('styles/style.css')

    user_info = get_user_by_matricola(matricola_utente)
    if user_info:
        nome_utente_autenticato = user_info['Nome Cognome']
    else:
        st.error("Errore critico: impossibile trovare i dati dell'utente loggato.")
        st.stop()

    today = datetime.date.today()
    start_sync_date = today.replace(day=1)
    end_sync_date = (start_sync_date + datetime.timedelta(days=35)).replace(day=1) + datetime.timedelta(days=31)

    if sync_oncall_shifts(start_date=start_sync_date, end_date=end_sync_date):
        st.toast("Calendario reperibilità sincronizzato.")

    if st.session_state.get('editing_turno_id'):
        render_edit_shift_form()
    elif st.session_state.get('debriefing_task'):
        knowledge_core = carica_knowledge_core()
        if knowledge_core:
            task_info = st.session_state.debriefing_task
            data_riferimento_attivita = task_info.get('data_attivita', datetime.date.today())
            render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento_attivita)
    else:
        if 'drawer_open' not in st.session_state:
            st.session_state.drawer_open = False
        if 'main_tab' not in st.session_state:
            st.session_state.main_tab = "Attività Assegnate"
        if 'expanded_menu' not in st.session_state:
            st.session_state.expanded_menu = "Attività"

        # App Bar
        unread_notifications = count_unread_notifications(matricola_utente)
        st.title(st.session_state.main_tab)
        if unread_notifications > 0:
            st.markdown(f'<div class="notification-badge">{unread_notifications}</div>', unsafe_allow_html=True)

        # Sidebar Navigation
        with st.sidebar:
            st.header(f"Ciao, {nome_utente_autenticato}!")
            st.caption(f"Ruolo: {ruolo}")

            user_notifications = leggi_notifiche(matricola_utente)
            render_notification_center(user_notifications, matricola_utente)

            last_login = get_last_login(matricola_utente)
            if last_login:
                last_login_dt = pd.to_datetime(last_login)
                st.caption(f"Ultimo accesso: {last_login_dt.strftime('%d/%m/%Y %H:%M')}")

            st.divider()

            # Top-level items
            if st.button("📝 Attività Assegnate", use_container_width=True):
                st.session_state.main_tab = "Attività Assegnate"
                st.session_state.navigated = True
                st.rerun()

            if st.button("🗂️ Storico", use_container_width=True):
                st.session_state.main_tab = "Storico"
                st.session_state.navigated = True
                st.rerun()

            st.divider()

            # Expandable sections
            expandable_menu_items = {
                "📅 Gestione": ["📅 Gestione Turni", "Richieste"],
            }
            if ruolo == "Amministratore":
                expandable_menu_items["⚙️ Amministrazione"] = ["Caposquadra", "Sistema"]

            for main_item, sub_items in expandable_menu_items.items():
                is_expanded = main_item == st.session_state.expanded_menu

                if st.button(main_item, use_container_width=True):
                    st.session_state.expanded_menu = main_item if not is_expanded else ""
                    st.session_state.navigated = True
                    st.rerun()

                if is_expanded:
                    for sub_item in sub_items:
                        if st.button(sub_item, key=f"nav_{sub_item}", use_container_width=True):
                            st.session_state.main_tab = sub_item
                            st.session_state.navigated = True
                            st.rerun()

            st.divider()
            if st.button("❓ Guida", use_container_width=True):
                st.session_state.main_tab = "❓ Guida"
                st.session_state.navigated = True
                st.rerun()
            if st.button("Disconnetti", use_container_width=True):
                token_to_delete = st.session_state.get('session_token')
                delete_session(token_to_delete)
                keys_to_clear = [k for k in st.session_state.keys()]
                for key in keys_to_clear:
                    del st.session_state[key]
                st.query_params.clear()
                st.rerun()

        st.header(f"Ciao, {nome_utente_autenticato}!")
        st.caption(f"Ruolo: {ruolo}")

        st.markdown('<div class="main-container">', unsafe_allow_html=True)

        oggi = datetime.date.today()

        df_contatti = get_all_users()
        attivita_da_recuperare = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)

        if 'main_tab' not in st.session_state:
            st.session_state.main_tab = "Attività Assegnate"

        main_tabs_list = ["Attività Assegnate", "📅 Gestione Turni", "Richieste", "Storico", "❓ Guida"]
        if ruolo == "Amministratore":
            if st.session_state.main_tab == "Caposquadra":
                selected_tab = "Dashboard Admin"
            elif st.session_state.main_tab == "Sistema":
                selected_tab = "Dashboard Admin"
            else:
                selected_tab = st.session_state.main_tab
        else:
            selected_tab = st.session_state.main_tab

        st.markdown('<div class="page-content">', unsafe_allow_html=True)

        df_contatti = get_all_users()

        if selected_tab == "Attività Assegnate":
            sub_tab_list = ["Attività di Oggi", "Recupero Attività", "Attività Validate"]
            if ruolo in ["Tecnico", "Amministratore"]:
                sub_tab_list.append("Compila Relazione")
            sub_tabs = st.tabs(sub_tab_list)

            with sub_tabs[0]:
                st.subheader(f"Attività del {oggi.strftime('%d/%m/%Y')}")
                lista_attivita_raw = trova_attivita(matricola_utente, oggi.day, oggi.month, oggi.year, df_contatti)
                for task in lista_attivita_raw:
                    task['data_attivita'] = oggi
                disegna_sezione_attivita(lista_attivita_raw, "today", ruolo)

            with sub_tabs[1]:
                st.subheader("Recupero Attività Non Rendicontate (Ultimi 30 Giorni)")
                attivita_da_recuperare = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)
                disegna_sezione_attivita(attivita_da_recuperare, "yesterday", ruolo)

            with sub_tabs[2]:
                st.subheader("Elenco Attività Validate")
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
            if ruolo in ["Tecnico", "Amministratore"] and len(sub_tabs) > 3:
                with sub_tabs[3]:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Compila Relazione di Reperibilità")

                    kb_count = get_report_knowledge_base_count()
                    if kb_count > 0:
                        st.caption(f"ℹ️ L'IA si basa su {kb_count} relazioni per la correzione.")
                    else:
                        st.caption("ℹ️ Base di conoscenza per l'IA non trovata o vuota.")

                    if 'relazione_testo' not in st.session_state: st.session_state.relazione_testo = ""
                    if 'relazione_partner' not in st.session_state: st.session_state.relazione_partner = None
                    if 'relazione_revisionata' not in st.session_state: st.session_state.relazione_revisionata = ""
                    if 'technical_suggestions' not in st.session_state: st.session_state.technical_suggestions = []

                    contatti_df = get_all_users()
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
                    st.markdown('</div>', unsafe_allow_html=True)
        elif selected_tab == "📅 Gestione Turni":
            render_gestione_turni_tab(matricola_utente, ruolo)
        elif selected_tab == "Richieste":
            render_richieste_tab(matricola_utente, ruolo, nome_utente_autenticato)
        elif selected_tab == "Storico":
            from pages.storico import render_storico_tab
            render_storico_tab()

        elif selected_tab == "❓ Guida":
            render_guida_tab(ruolo)

        elif selected_tab == "Dashboard Admin" and ruolo == "Amministratore":
            render_admin_dashboard(matricola_utente)

        st.markdown('</div>', unsafe_allow_html=True) # Close page-content
        st.markdown('</div>', unsafe_allow_html=True) # Close main-container
        st.markdown('</div>', unsafe_allow_html=True) # Close main-content

        if st.session_state.get('navigated'):
            st.components.v1.html("""
                <script>
                    setTimeout(() => {
                        window.parent.document.querySelector('[data-testid="stSidebar"] > div > div > button').click();
                    }, 100);
                </script>
            """, height=0)
            st.session_state.navigated = False

        st.markdown("""
            <script>
                const navLinks = window.parent.document.querySelectorAll(".nav-menu button");
                const pageContent = window.parent.document.querySelector(".page-content");

                navLinks.forEach(link => {
                    link.addEventListener("click", () => {
                        pageContent.classList.add("fade-out");
                        setTimeout(() => {
                        }, 200); // Corresponds to the CSS transition duration
                    });
                });
            </script>
        """, unsafe_allow_html=True)


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