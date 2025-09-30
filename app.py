import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import re
import os
import json
import uuid
from collections import defaultdict
import requests
import google.generativeai as genai
import win32com.client as win32
import matplotlib.pyplot as plt
import threading
import pythoncom # Necessario per la gestione di Outlook in un thread
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
    carica_archivio_completo,
    trova_attivita,
    scrivi_o_aggiorna_risposta,
    carica_dati_attivita_programmate,
    consolida_report_giornalieri
)
from modules.db_manager import (
    get_shifts_by_type, get_filtered_activities, get_technician_performance_data,
    get_interventions_for_technician, get_unvalidated_reports,
    create_validation_session, get_active_validation_session,
    update_validation_session_data, delete_validation_session,
    process_and_commit_validated_reports
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


# --- CONFIGURAZIONE ---
# Caricamento sicuro dei secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- CONFIGURAZIONE IA ---
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.error(f"Errore nella configurazione di Gemini: {e}")

# --- FUNZIONI DI SUPPORTO E CARICAMENTO DATI ---
@st.cache_resource
def autorizza_google():
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    if creds.access_token_expired:
        client.login()
    return client


# --- FUNZIONI DI ANALISI IA ---
@st.cache_data(show_spinner=False)
def analizza_storico_con_ia(_storico_df):
    if not GEMINI_API_KEY:
        return {"error": "La chiave API di Gemini non è configurata."}
    if _storico_df.empty or len(_storico_df) < 2 or _storico_df['Report'].dropna().empty:
        return {"info": "Dati storici insufficienti per un'analisi avanzata."}
    
    try:
        model = genai.GenerativeModel('models/gemini-flash-latest')
        base_prompt = """Sei un Direttore Tecnico di Manutenzione. Analizza la seguente cronologia di interventi e fornisci una diagnosi strategica in formato JSON con le chiavi "profilo", "diagnosi_tematica", "rischio_predittivo", "azione_strategica".

CRONOLOGIA:
"""
        storico_markdown = _storico_df[['Data_Riferimento', 'Tecnico', 'Stato', 'Report']].to_markdown(index=False)
        prompt = base_prompt + storico_markdown

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Errore durante l'analisi IA: {str(e)}"}

@st.cache_data(show_spinner=False)
def get_relevant_examples(user_text):
    """
    Carica l'indice della base di conoscenza e restituisce i 3 esempi più pertinenti.
    """
    import pickle
    from sklearn.metrics.pairwise import cosine_similarity

    index_filename = "knowledge_base_index.pkl"
    if not os.path.exists(index_filename):
        return None # L'indice non esiste

    with open(index_filename, 'rb') as f:
        data = pickle.load(f)

    vectorizer = data['vectorizer']
    matrix = data['matrix']
    sentences = data['sentences']

    # Vettorizza il testo dell'utente e trova i più simili
    user_vector = vectorizer.transform([user_text])
    similarities = cosine_similarity(user_vector, matrix).flatten()

    # Prendi i 3 indici più alti (escludendo somiglianze a zero)
    top_indices = similarities.argsort()[-3:][::-1]

    relevant_examples = [sentences[i] for i in top_indices if similarities[i] > 0]

    return "\n".join(relevant_examples)

from modules.instrumentation_logic import find_and_analyze_tags, get_technical_suggestions, analyze_domain_terminology

def revisiona_relazione_con_ia(_testo_originale, _knowledge_base):
    """
    Usa l'IA per revisionare una relazione tecnica, arricchendo la richiesta
    con analisi semantica della strumentazione basata su standard ISA S5.1.
    """
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
        model = genai.GenerativeModel('models/gemini-flash-latest')

        if technical_summary:
            # Prompt avanzato con contesto tecnico
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
            # Prompt standard se non viene trovato nessun tag strumentale
            knowledge_sample = get_relevant_examples(_testo_originale) or "Nessun esempio specifico trovato."
            prompt = f"""
            Sei un revisore esperto di relazioni tecniche in ambito industriale. Il tuo compito è revisionare e migliorare il seguente testo scritto da un tecnico, mantenendo un tono professionale, chiaro e conciso. Correggi eventuali errori grammaticali o di battitura e assicurati che lo stile sia coerente con gli esempi forniti.

            **STILE E TERMINOLOGIA DA SEGUIRE (ESEMPI):**
            ---
            {knowledge_sample}
            ---

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


# --- FUNZIONI INTERFACCIA UTENTE ---
def visualizza_storico_organizzato(storico_list, pdl):
    if storico_list:
        with st.expander(f"Mostra cronologia interventi per PdL {pdl}", expanded=True):
            for intervento in storico_list:
                intervento['data_dt'] = pd.to_datetime(intervento.get('Data_Riferimento'), dayfirst=True, errors='coerce')
            
            storico_filtrato = [i for i in storico_list if pd.notna(i['data_dt'])]
            if not storico_filtrato:
                st.info("Nessun intervento con data valida trovato.")
                return

            interventi_per_data = defaultdict(list)
            for intervento in storico_filtrato:
                interventi_per_data[intervento['data_dt'].strftime('%d/%m/%Y')].append(intervento)
            
            date_ordinate = sorted(interventi_per_data.keys(), key=lambda x: datetime.datetime.strptime(x, '%d/%m/%Y'), reverse=True)

            for data in date_ordinate:
                with st.expander(f"Interventi del **{data}**"):
                    for intervento_singolo in interventi_per_data[data]:
                        st.markdown(f"**Tecnico:** {intervento_singolo.get('Tecnico', 'N/D')} - **Stato:** {intervento_singolo.get('Stato', 'N/D')}")
                        st.markdown("**Report:**")
                        st.info(f"{intervento_singolo.get('Report', 'Nessun report.')}")
                        st.markdown("---")
    else:
        st.markdown("*Nessuno storico disponibile per questo PdL.*")

def disegna_sezione_attivita(lista_attivita, section_key, ruolo_utente):
    if f"completed_tasks_{section_key}" not in st.session_state:
        st.session_state[f"completed_tasks_{section_key}"] = []

    completed_pdls = {task['pdl'] for task in st.session_state.get(f"completed_tasks_{section_key}", [])}
    attivita_da_fare = [task for task in lista_attivita if task['pdl'] not in completed_pdls]

    st.subheader("📝 Attività da Compilare")
    if not attivita_da_fare:
        st.info("Tutte le attività per questa sezione sono state compilate.")
    
    for i, task in enumerate(attivita_da_fare):
        with st.container(border=True):
            # Aggiungi la data se presente (per le attività recuperate)
            date_display = ""
            if 'data_attivita' in task:
                date_display = f" del **{task['data_attivita'].strftime('%d/%m/%Y')}**"

            st.markdown(f"**PdL `{task['pdl']}`** - {task['attivita']}{date_display}")

            # --- LOGICA TEAM ---
            team = task.get('team', [])
            if len(team) > 1:
                team_details_md = "**Team:**\n"
                for member in team:
                    orari_str = ", ".join(member['orari'])
                    team_details_md += f"- {member['nome']} ({member['ruolo']}) | 🕒 {orari_str}\n"
                st.info(team_details_md)
            # --- FINE LOGICA TEAM ---
            
            visualizza_storico_organizzato(task.get('storico', []), task['pdl'])
            if task.get('storico'):
                if st.button("🤖 Genera Diagnosi Avanzata", key=f"ia_{section_key}_{i}", help="Usa l'IA per analizzare lo storico"):
                    with st.spinner("L'analista IA sta esaminando lo storico..."):
                        analisi = analizza_storico_con_ia(pd.DataFrame(task['storico']))
                        st.session_state[f"analisi_{section_key}_{i}"] = analisi
                if f"analisi_{section_key}_{i}" in st.session_state:
                    analisi = st.session_state[f"analisi_{section_key}_{i}"]
                    if "error" in analisi: st.error(f"**Errore IA:** {analisi['error']}")
                    elif "info" in analisi: st.info(analisi["info"])
                    else:
                        st.write(f"**Profilo:** {analisi.get('profilo', 'N/D')}")
                        st.write(f"**Diagnosi:** {analisi.get('diagnosi_tematica', 'N/D')}")
                        st.info(f"**Azione Strategica:** {analisi.get('azione_strategica', 'N/D')}")
            
            st.markdown("---")
            # --- LOGICA RUOLO ---
            if len(task.get('team', [])) > 1 and ruolo_utente == "Aiutante":
                st.warning("ℹ️ Solo i tecnici possono compilare il report per questa attività di team.")
            else:
                col1, col2 = st.columns(2)
                if col1.button("✍️ Compila Report Guidato (IA)", key=f"guide_{section_key}_{i}"):
                    st.session_state.debriefing_task = {**task, "section_key": section_key}
                    st.session_state.report_mode = 'guided'
                    st.rerun()
                if col2.button("📝 Compila Report Manuale", key=f"manual_{section_key}_{i}"):
                    st.session_state.debriefing_task = {**task, "section_key": section_key}
                    st.session_state.report_mode = 'manual'
                    st.rerun()
            # --- FINE LOGICA RUOLO ---
    
    st.divider()

    if st.session_state.get(f"completed_tasks_{section_key}", []):
        with st.expander("✅ Attività Inviate (Modificabili)", expanded=False):
            for i, task_data in enumerate(st.session_state[f"completed_tasks_{section_key}"]):
                with st.container(border=True):
                    st.markdown(f"**PdL `{task_data['pdl']}`** - {task_data['stato']}")
                    st.caption("Report Inviato:")
                    st.info(task_data['report'])
                    if st.button("Modifica Report", key=f"edit_{section_key}_{i}"):
                        st.session_state.debriefing_task = task_data
                        st.session_state.report_mode = 'manual'
                        st.rerun()

def render_notification_center(notifications_df, gestionale_data, matricola_utente):
    unread_count = len(notifications_df[notifications_df['Stato'] == 'non letta'])
    icon_label = f"🔔 {unread_count}" if unread_count > 0 else "🔔"

    with st.popover(icon_label):
        st.subheader("Notifiche")
        if notifications_df.empty:
            st.write("Nessuna notifica.")
        else:
            for _, notifica in notifications_df.iterrows():
                notifica_id = notifica['ID_Notifica']
                is_unread = notifica['Stato'] == 'non letta'

                col1, col2 = st.columns([4, 1])
                with col1:
                    if is_unread:
                        st.markdown(f"**{notifica['Messaggio']}**")
                    else:
                        st.markdown(f"<span style='color: grey;'>{notifica['Messaggio']}</span>", unsafe_allow_html=True)
                    st.caption(pd.to_datetime(notifica['Timestamp']).strftime('%d/%m/%Y %H:%M'))

                with col2:
                    if is_unread:
                        if st.button(" letto", key=f"read_{notifica_id}", help="Segna come letto"):
                            segna_notifica_letta(gestionale_data, notifica_id)
                            salva_gestionale_async(gestionale_data)
                            st.rerun()
                st.divider()

def render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento):
    task = st.session_state.debriefing_task
    section_key = task['section_key']

    def handle_submit(report_text, stato, answers_dict=None):
        if report_text.strip():
            if answers_dict and 'equipment' in answers_dict and answers_dict['equipment'].startswith("Altro:"):
                report_lines = {k: v for k, v in answers_dict.items() if k != 'equipment'}
                learning_module.add_new_entry(
                    pdl=task['pdl'],
                    attivita=task['attivita'],
                    report_lines=report_lines,
                    tecnico=matricola_utente
                )
                st.info("💡 La tua segnalazione per 'Altro' è stata registrata e sarà usata per migliorare il sistema.")

            dati = {
                'descrizione': f"PdL {task['pdl']} - {task['attivita']}",
                'report': report_text,
                'stato': stato
            }

            # La nuova funzione scrive direttamente nel DB e non ha più bisogno del client_google o del row_index
            success = scrivi_o_aggiorna_risposta(dati, matricola_utente, data_riferimento)

            if success:
                completed_task_data = {**task, 'report': report_text, 'stato': stato, 'answers': answers_dict}
                
                completed_list = st.session_state.get(f"completed_tasks_{section_key}", [])
                completed_list = [t for t in completed_list if t['pdl'] != task['pdl']]
                completed_list.append(completed_task_data)
                st.session_state[f"completed_tasks_{section_key}"] = completed_list

                if section_key == 'yesterday':
                    if 'completed_tasks_yesterday' not in st.session_state:
                        st.session_state.completed_tasks_yesterday = []
                    st.session_state.completed_tasks_yesterday.append(completed_task_data)

                st.success("Report inviato con successo al database!")
                del st.session_state.debriefing_task
                if 'answers' in st.session_state: del st.session_state.answers
                st.balloons()
                st.rerun()
            else:
                st.error("Si è verificato un errore durante il salvataggio del report nel database.")
        else:
            st.warning("Il report non può essere vuoto.")

    # Il resto della funzione 'render_debriefing_ui' continua da qui...
    if st.session_state.report_mode == 'manual':
        st.title("📝 Compilazione Manuale")
        st.subheader(f"PdL `{task['pdl']}` - {task['attivita']}")
        report_text = st.text_area("Inserisci il tuo report qui:", value=task.get('report', ''), height=200)
        stato_options = ["TERMINATA", "SOSPESA", "IN CORSO", "NON SVOLTA"]
        stato_index = stato_options.index(task.get('stato')) if task.get('stato') in stato_options else 0
        stato = st.selectbox("Stato Finale", stato_options, index=stato_index, key="manual_stato")
        
        col1, col2 = st.columns(2)
        if col1.button("Invia Report", type="primary"):
            handle_submit(report_text, stato)
        if col2.button("Annulla"):
            del st.session_state.debriefing_task; st.rerun()
        return

    st.title("✍️ Debriefing Guidato (IA)")
    st.subheader(f"PdL `{task['pdl']}` - {task['attivita']}")

    is_editing = bool(task.get('answers'))

    if 'answers' not in st.session_state:
        st.session_state.answers = task.get('answers', {}) if is_editing else {}
        if not st.session_state.answers:
            for key in knowledge_core:
                if key.replace("_", " ") in task['attivita'].lower():
                    st.session_state.answers['equipment'] = knowledge_core[key]['display_name']; break
    
    answers = st.session_state.answers
    
    if 'equipment' not in answers:
        st.markdown("#### 1. Attrezzatura gestita?")
        cols = st.columns(len(knowledge_core))
        for i, (key, value) in enumerate(knowledge_core.items()):
            if cols[i].button(value['display_name'], key=f"eq_{key}"):
                answers['equipment'] = value['display_name']; st.rerun()
        other_input = st.text_input("Altra attrezzatura (specificare)", key="eq_other")
        if st.button("Conferma Altro", key="conf_eq_other") and other_input:
            answers['equipment'] = f"Altro: {other_input}"; st.rerun()
        if st.button("Torna alla lista attività"):
            del st.session_state.debriefing_task; st.rerun()
        return

    equipment_name = answers['equipment'].split(': ')[-1]
    equipment_key = next((k for k, v in knowledge_core.items() if v['display_name'] == equipment_name), None)
    
    final_report_text = ""
    
    if not equipment_key:
        st.info(f"Hai specificato un'attrezzatura non standard: **{equipment_name}**")
        final_report_text = st.text_area("Descrivi l'intervento eseguito:", value=answers.get('report_text', ''), height=150, key="other_equip_report")
    else:
        equipment = knowledge_core[equipment_key]
        path_key = answers.get('Tipo', 'root')
        questions = equipment.get('questions', []) + equipment.get('paths', {}).get(path_key.lower().replace(" / ", "_").split(' ')[0], {}).get('questions', [])
        
        for i, q in enumerate(questions):
            q_id = q['id']
            if q_id.capitalize() not in answers:
                st.markdown(f"#### {i + 2}. {q['text']}")
                options = list(q['options'].values())
                cols = st.columns(len(options))
                for j, opt_val in enumerate(options):
                    if cols[j].button(opt_val, key=f"{q_id}_{j}"):
                        answers[q_id.capitalize()] = opt_val; st.rerun()
                other_input = st.text_input("Altro (specificare e confermare)", key=f"{q_id}_other")
                if st.button("Conferma Altro", key=f"conf_{q_id}") and other_input:
                    answers[q_id.capitalize()] = f"Altro: {other_input}"; st.rerun()
                if st.button("Torna alla lista attività"):
                    del st.session_state.debriefing_task; st.rerun()
                return
        
        st.success("Tutte le domande completate!")
        final_report_lines = [f"- **{k}:** {v}" for k, v in answers.items() if k != 'equipment']
        final_report_text = "\n".join(final_report_lines)
        st.markdown("---"); st.subheader("Riepilogo Report Generato")
        st.markdown(f"**Attrezzatura:** {answers['equipment']}\n{final_report_text}")

    stato_options = ["TERMINATA", "SOSPESA", "IN CORSO", "NON SVOLTA"]
    stato_index = stato_options.index(task.get('stato')) if task.get('stato') in stato_options else 0
    stato = st.selectbox("Stato Finale", stato_options, index=stato_index)
    
    col1, col2 = st.columns(2)
    if col1.button("✅ Invia Report", type="primary"):
        full_report_str = f"Attrezzatura: {answers.get('equipment', 'N/D')}\n{final_report_text}"
        handle_submit(full_report_str, stato, answers)
    if col2.button("Annulla"):
        del st.session_state.debriefing_task; 
        if 'answers' in st.session_state: del st.session_state.answers
        st.rerun()


def render_edit_shift_form(gestionale_data):
    turno_id = st.session_state['editing_turno_id']
    df_turni = gestionale_data['turni']

    try:
        turno_data = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    except (IndexError, KeyError):
        st.error("Errore: Turno non trovato o dati corrotti.")
        if 'editing_turno_id' in st.session_state:
            del st.session_state['editing_turno_id']
        st.rerun()

    st.title(f"Modifica Turno: {turno_data.get('Descrizione', 'N/D')}")

    with st.form("edit_shift_form"):
        st.subheader("Dettagli Turno")

        # Pre-fill form with existing data
        tipi_turno = ["Assistenza", "Straordinario"]
        try:
            tipo_turno_index = tipi_turno.index(turno_data.get('Tipo', 'Assistenza'))
        except ValueError:
            tipo_turno_index = 0 # Default to Assistenza if value is invalid

        tipo_turno = st.selectbox("Tipo Turno", tipi_turno, index=tipo_turno_index)

        desc_turno = st.text_input("Descrizione Turno", value=turno_data.get('Descrizione', ''))

        try:
            default_date = pd.to_datetime(turno_data['Data']).date()
        except (ValueError, TypeError):
            default_date = datetime.date.today()
        data_turno = st.date_input("Data Turno", value=default_date)

        col1, col2 = st.columns(2)
        with col1:
            try:
                default_start_time = datetime.datetime.strptime(str(turno_data['OrarioInizio']), '%H:%M').time()
            except (ValueError, TypeError):
                default_start_time = datetime.time(8, 0)
            ora_inizio = st.time_input("Orario Inizio", value=default_start_time)
        with col2:
            try:
                default_end_time = datetime.datetime.strptime(str(turno_data['OrarioFine']), '%H:%M').time()
            except (ValueError, TypeError):
                default_end_time = datetime.time(17, 0)
            ora_fine = st.time_input("Orario Fine", value=default_end_time)

        col3, col4 = st.columns(2)
        with col3:
            posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1, value=int(turno_data.get('PostiTecnico', 0)))
        with col4:
            posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1, value=int(turno_data.get('PostiAiutante', 0)))

        st.subheader("Gestione Personale")

        df_prenotazioni = gestionale_data['prenotazioni']
        df_contatti = gestionale_data['contatti']

        personale_nel_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
        tecnici_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Tecnico']['Matricola'].tolist()
        aiutanti_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Aiutante']['Matricola'].tolist()

        # Crea una mappa Matricola -> Nome Cognome per la visualizzazione
        matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola']).to_dict()

        tecnici_selezionati = st.multiselect("Seleziona Tecnici Assegnati", options=df_contatti['Matricola'].tolist(), default=tecnici_nel_turno, format_func=lambda x: matricola_to_name.get(x, x), key="edit_tecnici")
        aiutanti_selezionati = st.multiselect("Seleziona Aiutanti Assegnati", options=df_contatti['Matricola'].tolist(), default=aiutanti_nel_turno, format_func=lambda x: matricola_to_name.get(x, x), key="edit_aiutanti")


        # Form submission buttons
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("Salva Modifiche")
        with col_cancel:
            if st.form_submit_button("Annulla", type="secondary"):
                del st.session_state['editing_turno_id']
                st.rerun()

    if submitted:
        # --- LOGICA DI AGGIORNAMENTO ---

        # 1. Aggiorna i dettagli del turno nel DataFrame dei turni
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Descrizione'] = desc_turno
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Data'] = pd.to_datetime(data_turno)
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'OrarioInizio'] = ora_inizio.strftime('%H:%M')
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'OrarioFine'] = ora_fine.strftime('%H:%M')
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'PostiTecnico'] = posti_tech
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'PostiAiutante'] = posti_aiut
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Tipo'] = tipo_turno

        # 2. Calcola le modifiche al personale e registra i log
        personale_originale = set(personale_nel_turno['Matricola'].tolist())
        personale_nuovo = set(tecnici_selezionati + aiutanti_selezionati)
        admin_user_matricola = st.session_state.get('authenticated_user', 'N/D')

        personale_rimosso = personale_originale - personale_nuovo
        for matricola in personale_rimosso:
            log_shift_change(gestionale_data, turno_id, "Rimozione Admin", matricola_originale=matricola, matricola_eseguito_da=admin_user_matricola)

        personale_aggiunto = personale_nuovo - personale_originale
        for matricola in personale_aggiunto:
            log_shift_change(gestionale_data, turno_id, "Aggiunta Admin", matricola_subentrante=matricola, matricola_eseguito_da=admin_user_matricola)

        # 3. Aggiorna le prenotazioni
        # Rimuovi tutte le vecchie prenotazioni per questo turno
        gestionale_data['prenotazioni'] = gestionale_data['prenotazioni'][gestionale_data['prenotazioni']['ID_Turno'] != turno_id]

        # Aggiungi le nuove prenotazioni aggiornate
        nuove_prenotazioni_list = []
        for matricola in tecnici_selezionati:
            nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{matricola}", 'ID_Turno': turno_id, 'Matricola': matricola, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()})
        for matricola in aiutanti_selezionati:
             nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{matricola}", 'ID_Turno': turno_id, 'Matricola': matricola, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()})

        if nuove_prenotazioni_list:
            df_nuove_prenotazioni = pd.DataFrame(nuove_prenotazioni_list)
            gestionale_data['prenotazioni'] = pd.concat([gestionale_data['prenotazioni'], df_nuove_prenotazioni], ignore_index=True)

        # 4. Invia notifiche per il personale rimosso
        for matricola in personale_rimosso:
            messaggio = f"Sei stato rimosso dal turno '{desc_turno}' del {data_turno.strftime('%d/%m/%Y')} dall'amministratore."
            crea_notifica(gestionale_data, matricola, messaggio)

        # 5. Salva le modifiche e termina la modalità di modifica
        if salva_gestionale_async(gestionale_data):
            st.success("Turno aggiornato con successo!")
            st.toast("Le modifiche sono state salvate.")
            del st.session_state['editing_turno_id']
            st.rerun()
        else:
            st.error("Si è verificato un errore durante il salvataggio delle modifiche.")

def render_turni_list(df_turni, gestionale, matricola_utente, ruolo, key_suffix):
    """
    Renderizza una lista di turni, con la logica per la prenotazione, cancellazione e sostituzione.
    """
    if df_turni.empty:
        st.info("Nessun turno di questo tipo disponibile al momento.")
        return

    mostra_solo_disponibili = st.checkbox("Mostra solo turni con posti disponibili", key=f"filter_turni_{key_suffix}")

    if ruolo == "Amministratore":
        search_term_turni = st.text_input("Cerca per descrizione del turno...", key=f"search_turni_{key_suffix}")
        if search_term_turni:
            df_turni = df_turni[df_turni['Descrizione'].str.contains(search_term_turni, case=False, na=False)]

    st.divider()

    if df_turni.empty:
        st.info("Nessun turno corrisponde alla ricerca.")

    for index, turno in df_turni.iterrows():
        prenotazioni_turno = gestionale['prenotazioni'][gestionale['prenotazioni']['ID_Turno'] == turno['ID_Turno']]
        posti_tecnico = int(turno['PostiTecnico'])
        posti_aiutante = int(turno['PostiAiutante'])
        tecnici_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Tecnico'])
        aiutanti_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Aiutante'])

        is_available = (tecnici_prenotati < posti_tecnico) or (aiutanti_prenotati < posti_aiutante)
        if mostra_solo_disponibili and not is_available:
            continue

        with st.container(border=True):
            st.markdown(f"**{turno['Descrizione']}**")
            st.caption(f"{pd.to_datetime(turno['Data']).strftime('%d/%m/%Y')} | {turno['OrarioInizio']} - {turno['OrarioFine']}")

            tech_icon = "✅" if tecnici_prenotati < posti_tecnico else "❌"
            aiut_icon = "✅" if aiutanti_prenotati < posti_aiutante else "❌"
            st.markdown(f"**Posti:** `Tecnici: {tecnici_prenotati}/{posti_tecnico}` {tech_icon} | `Aiutanti: {aiutanti_prenotati}/{posti_aiutante}` {aiut_icon}")

            if not prenotazioni_turno.empty:
                st.markdown("**Personale Prenotato:**")
                df_contatti = gestionale.get('contatti', pd.DataFrame())
                matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola'].astype(str)).to_dict()

                for _, p in prenotazioni_turno.iterrows():
                    matricola = str(p['Matricola'])
                    nome_utente = matricola_to_name.get(matricola, f"Matricola {matricola}")
                    ruolo_utente_turno = p['RuoloOccupato']

                    user_details = df_contatti[df_contatti['Matricola'] == matricola]
                    is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('PasswordHash'))

                    display_name = f"*{nome_utente} (Esterno)*" if is_placeholder else nome_utente
                    st.markdown(f"- {display_name} (*{ruolo_utente_turno}*)", unsafe_allow_html=True)

            st.markdown("---")

            if ruolo == "Amministratore":
                if st.button("✏️ Modifica Turno", key=f"edit_{turno['ID_Turno']}_{key_suffix}"):
                    st.session_state['editing_turno_id'] = turno['ID_Turno']
                    st.rerun()
                st.markdown("---")

            prenotazione_utente = prenotazioni_turno[prenotazioni_turno['Matricola'] == str(matricola_utente)]

            if not prenotazione_utente.empty:
                st.success("Sei prenotato per questo turno.")

                # Logica di conferma per azioni critiche
                if 'confirm_action' not in st.session_state:
                    st.session_state.confirm_action = None

                is_confirmation_pending = st.session_state.confirm_action and st.session_state.confirm_action.get('turno_id') == turno['ID_Turno']

                if is_confirmation_pending:
                    action_type = st.session_state.confirm_action['type']
                    if action_type == 'cancel':
                        st.warning("❓ Sei sicuro di voler cancellare la tua prenotazione?")
                    elif action_type == 'publish':
                        st.warning("❓ Sei sicuro di voler pubblicare il tuo turno in bacheca?")

                    col_yes, col_no, col_spacer = st.columns([1, 1, 2])
                    with col_yes:
                        if st.button("✅ Sì", key=f"confirm_yes_{turno['ID_Turno']}", width='stretch'):
                            success = False
                            if action_type == 'cancel':
                                if cancella_prenotazione_logic(gestionale, matricola_utente, turno['ID_Turno']):
                                    success = True
                            elif action_type == 'publish':
                                if pubblica_turno_in_bacheca_logic(gestionale, matricola_utente, turno['ID_Turno']):
                                    success = True

                            if success:
                                salva_gestionale_async(gestionale)

                            st.session_state.confirm_action = None
                            st.rerun()
                    with col_no:
                        if st.button("❌ No", key=f"confirm_no_{turno['ID_Turno']}", width='stretch'):
                            st.session_state.confirm_action = None
                            st.rerun()
                else:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Cancella Prenotazione", key=f"del_{turno['ID_Turno']}_{key_suffix}", help="Rimuove la tua prenotazione dal turno."):
                            st.session_state.confirm_action = {'type': 'cancel', 'turno_id': turno['ID_Turno']}
                            st.rerun()
                    with col2:
                        if st.button("📢 Pubblica in Bacheca", key=f"pub_{turno['ID_Turno']}_{key_suffix}", help="Rilascia il tuo turno e rendilo disponibile a tutti in bacheca."):
                            st.session_state.confirm_action = {'type': 'publish', 'turno_id': turno['ID_Turno']}
                            st.rerun()
                    with col3:
                        if st.button("🔄 Chiedi Sostituzione", key=f"ask_{turno['ID_Turno']}_{key_suffix}", help="Chiedi a un collega specifico di sostituirti."):
                            st.session_state['sostituzione_turno_id'] = turno['ID_Turno']
                            st.rerun()
            else:
                opzioni = []
                if tecnici_prenotati < posti_tecnico: opzioni.append("Tecnico")
                if aiutanti_prenotati < posti_aiutante: opzioni.append("Aiutante")
                if opzioni:
                    ruolo_scelto = st.selectbox("Prenota come:", opzioni, key=f"sel_{turno['ID_Turno']}_{key_suffix}")
                    if st.button("Conferma Prenotazione", key=f"add_{turno['ID_Turno']}_{key_suffix}"):
                        if prenota_turno_logic(gestionale, matricola_utente, turno['ID_Turno'], ruolo_scelto):
                            salva_gestionale_async(gestionale); st.rerun()
                else:
                    st.warning("Turno al completo.")
                    if st.button("Chiedi Sostituzione", key=f"ask_full_{turno['ID_Turno']}_{key_suffix}"):
                        st.session_state['sostituzione_turno_id'] = turno['ID_Turno']; st.rerun()

            if st.session_state.get('sostituzione_turno_id') == turno['ID_Turno']:
                st.markdown("---")
                st.markdown("**A chi vuoi chiedere il cambio?**")

                matricola_to_name = pd.Series(gestionale['contatti']['Nome Cognome'].values, index=gestionale['contatti']['Matricola'].astype(str)).to_dict()

                # Opzioni per la sostituzione: o chi è già nel turno, o tutti i contatti
                if not prenotazione_utente.empty:
                    ricevente_options = prenotazioni_turno['Matricola'].tolist()
                else:
                    ricevente_options = gestionale['contatti']['Matricola'].tolist()

                ricevente_options = [str(m) for m in ricevente_options if str(m) != str(matricola_utente)] # Escludi te stesso

                ricevente_matricola = st.selectbox("Seleziona collega:", ricevente_options, format_func=lambda m: matricola_to_name.get(m, m), key=f"swap_select_{turno['ID_Turno']}_{key_suffix}")

                if st.button("Invia Richiesta", key=f"swap_confirm_{turno['ID_Turno']}_{key_suffix}"):
                    if richiedi_sostituzione_logic(gestionale, matricola_utente, ricevente_matricola, turno['ID_Turno']):
                        salva_gestionale_async(gestionale); del st.session_state['sostituzione_turno_id']; st.rerun()

def render_gestione_account(gestionale_data):
    df_contatti = gestionale_data['contatti']

    # --- Modifica Utenti Esistenti ---
    st.subheader("Modifica Utenti Esistenti")

    search_term = st.text_input("Cerca utente per nome o matricola...", key="user_search_admin")
    if search_term:
        df_contatti = df_contatti[
            df_contatti['Nome Cognome'].str.contains(search_term, case=False, na=False) |
            df_contatti['Matricola'].astype(str).str.contains(search_term, case=False, na=False)
        ]

    if 'editing_user_matricola' not in st.session_state:
        st.session_state.editing_user_matricola = None

    # Se un utente è in modifica, mostra solo il form di modifica
    if st.session_state.editing_user_matricola:
        user_to_edit_series = df_contatti[df_contatti['Matricola'] == st.session_state.editing_user_matricola]
        if not user_to_edit_series.empty:
            user_to_edit = user_to_edit_series.iloc[0]
            user_name = user_to_edit['Nome Cognome']
            with st.form(key="edit_user_form"):
                st.subheader(f"Modifica Utente: {user_name} ({st.session_state.editing_user_matricola})")

                ruoli_disponibili = ["Tecnico", "Aiutante", "Amministratore"]
                try:
                    current_role_index = ruoli_disponibili.index(user_to_edit['Ruolo'])
                except ValueError:
                    current_role_index = 0 # Default a Tecnico se il ruolo non è standard

                new_role = st.selectbox("Nuovo Ruolo", options=ruoli_disponibili, index=current_role_index)

                is_placeholder_current = pd.isna(user_to_edit.get('PasswordHash'))
                is_placeholder_new = st.checkbox("Resetta Account (forza creazione nuova password)", value=is_placeholder_current)

                new_password = ""
                if not is_placeholder_new:
                    new_password = st.text_input("Nuova Password (lasciare vuoto per non modificare)", type="password")

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Salva Modifiche", type="primary"):
                        user_idx = df_contatti[df_contatti['Matricola'] == st.session_state.editing_user_matricola].index[0]
                        df_contatti.loc[user_idx, 'Ruolo'] = new_role

                        if is_placeholder_new:
                            df_contatti.loc[user_idx, 'PasswordHash'] = None
                            st.success(f"Account di {user_name} resettato. Dovrà creare una nuova password al prossimo accesso.")
                        elif new_password:
                            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                            df_contatti.loc[user_idx, 'PasswordHash'] = hashed.decode('utf-8')
                            st.success(f"Password per {user_name} aggiornata.")

                        salva_gestionale_async(gestionale_data)
                        st.session_state.editing_user_matricola = None
                        st.toast("Modifiche salvate!")
                        st.rerun()

                with col2:
                    if st.form_submit_button("Annulla"):
                        st.session_state.editing_user_matricola = None
                        st.rerun()
        else:
            st.error("Utente non trovato. Ricaricamento...")
            st.session_state.editing_user_matricola = None
            st.rerun()

    # Altrimenti, mostra la lista di tutti gli utenti
    else:
        for index, user in df_contatti.iterrows():
            user_name = user['Nome Cognome']
            user_matricola = user['Matricola']
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{user_name}** (`{user_matricola}`)")
                with col2:
                    is_placeholder = pd.isna(user.get('PasswordHash'))
                    status = "Da Attivare (primo accesso)" if is_placeholder else "Attivo"
                    st.markdown(f"*{user['Ruolo']}* - Stato: *{status}*")
                with col3:
                    if st.button("Modifica", key=f"edit_{user_matricola}"):
                        st.session_state.editing_user_matricola = user_matricola
                        st.rerun()

                # Aggiungi colonna per reset 2FA
                has_2fa = '2FA_Secret' in user and pd.notna(user['2FA_Secret']) and user['2FA_Secret']
                if has_2fa:
                    with col1:
                        if st.button("Resetta 2FA", key=f"reset_2fa_{user_matricola}", help="Rimuove la 2FA per questo utente. Dovrà configurarla di nuovo al prossimo accesso."):
                            user_idx = df_contatti[df_contatti['Matricola'] == user_matricola].index[0]
                            df_contatti.loc[user_idx, '2FA_Secret'] = None
                            salva_gestionale_async(gestionale_data)
                            st.success(f"2FA resettata per {user_name}.")
                            st.rerun()

    st.divider()

    # --- Crea Nuovo Utente ---
    with st.expander("Crea Nuovo Utente"):
        with st.form("new_user_form", clear_on_submit=True):
            st.subheader("Dati Nuovo Utente")
            c1, c2, c3 = st.columns(3)
            new_nome = c1.text_input("Nome*")
            new_cognome = c2.text_input("Cognome*")
            new_matricola = c3.text_input("Matricola*")
            new_ruolo = st.selectbox("Ruolo", ["Tecnico", "Aiutante", "Amministratore"])

            submitted_new_user = st.form_submit_button("Crea Utente")

            if submitted_new_user:
                if new_nome and new_cognome and new_matricola:
                    if str(new_matricola) in df_contatti['Matricola'].astype(str).tolist():
                        st.error(f"Errore: La matricola '{new_matricola}' esiste già.")
                    else:
                        nome_completo = f"{new_nome.strip()} {new_cognome.strip()}"
                        new_user_data = {
                            'Matricola': str(new_matricola),
                            'Nome Cognome': nome_completo,
                            'Ruolo': new_ruolo,
                            'PasswordHash': None,
                            'Link Attività': ''
                        }
                        # Assicura che tutte le colonne esistenti siano presenti per evitare errori di concat
                        for col in df_contatti.columns:
                            if col not in new_user_data:
                                new_user_data[col] = None

                        nuovo_utente_df = pd.DataFrame([new_user_data])
                        gestionale_data['contatti'] = pd.concat([df_contatti, nuovo_utente_df], ignore_index=True)

                        if salva_gestionale_async(gestionale_data):
                            st.success(f"Utente '{nome_completo}' creato con successo! Dovrà impostare la password al primo accesso.")
                            st.rerun()
                        else:
                            st.error("Errore durante il salvataggio del nuovo utente.")
                else:
                    st.warning("Nome, Cognome e Matricola sono obbligatori.")


def render_technician_detail_view():
    """Mostra la vista di dettaglio per un singolo tecnico."""
    technician_matricola = st.session_state['detail_technician_matricola']
    start_date = st.session_state['detail_start_date']
    end_date = st.session_state['detail_end_date']

    # Recupera il nome del tecnico dalla matricola per la visualizzazione
    df_contatti = carica_gestionale()['contatti']
    technician_name = df_contatti[df_contatti['Matricola'] == technician_matricola].iloc[0]['Nome Cognome']

    st.title(f"Dettaglio Performance: {technician_name}")
    st.markdown(f"Periodo: **{start_date.strftime('%d/%m/%Y')}** - **{end_date.strftime('%d/%m/%Y')}**")

    # Recupera le metriche già calcolate dalla sessione
    if 'performance_results' in st.session_state:
        performance_df = st.session_state['performance_results']['df']
        if technician_name in performance_df.index:
            technician_metrics = performance_df.loc[technician_name]
            
            # Mostra le metriche specifiche per il tecnico
            st.markdown("#### Riepilogo Metriche")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Totale Interventi", technician_metrics['Totale Interventi'])
            c2.metric("Tasso Completamento", f"{technician_metrics['Tasso Completamento (%)']}%")
            c3.metric("Ritardo Medio (gg)", technician_metrics['Ritardo Medio Compilazione (gg)'])
            c4.metric("Report Sbrigativi", technician_metrics['Report Sbrigativi'])
            st.markdown("---")

    if st.button("⬅️ Torna alla Dashboard"):
        del st.session_state['detail_technician_matricola']
        del st.session_state['detail_start_date']
        del st.session_state['detail_end_date']
        st.rerun()

    # Utilizza la nuova funzione per caricare i dati in modo efficiente
    technician_interventions = get_interventions_for_technician(technician_matricola, start_date, end_date)


    if technician_interventions.empty:
        st.warning("Nessun intervento trovato per questo tecnico nel periodo selezionato.")
        return

    st.markdown("### Riepilogo Interventi")
    # Formatta la colonna della data prima di visualizzarla
    technician_interventions['Data'] = pd.to_datetime(technician_interventions['Data_Riferimento_dt']).dt.strftime('%d/%m/%Y')
    st.dataframe(technician_interventions[['Data', 'PdL', 'Descrizione', 'Stato', 'Report']])

    st.download_button(
        label="📥 Esporta Dettaglio CSV",
        data=to_csv(technician_interventions),
        file_name=f"dettaglio_{technician_name}.csv",
        mime='text/csv',
    )

    # --- ANALISI AVANZATA ---
    st.markdown("---")
    st.markdown("### Analisi Avanzata")
    
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Ripartizione Esiti")
        status_counts = technician_interventions['Stato'].value_counts()
        if not status_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
            st.pyplot(fig)
        else:
            st.info("Nessun dato sullo stato disponibile per creare il grafico.")

    with col2:
        st.markdown("#### Andamento Attività nel Tempo")
        interventions_by_day = technician_interventions.groupby(pd.to_datetime(technician_interventions['Data_Riferimento_dt']).dt.date).size()
        interventions_by_day.index.name = 'Data'
        st.bar_chart(interventions_by_day)

    # Sezione per i report sbrigativi
    st.markdown("#### Analisi Qualitativa: Report Sbrigativi")
    rushed_reports_df = technician_interventions[technician_interventions['Report'].str.len() < 20]
    if not rushed_reports_df.empty:
        st.warning(f"Trovati {len(rushed_reports_df)} report potenzialmente sbrigativi:")
        for _, row in rushed_reports_df.iterrows():
            st.info(f"**Data:** {row['Data']} - **PdL:** {row['PdL']} - **Report:** *'{row['Report']}'*")
    else:
        st.success("Nessun report sbrigativo trovato in questo periodo.")

def render_report_validation_tab(user_matricola):
    st.subheader("Validazione Report Tecnici")
    st.info("""
    Questa sezione permette di validare i report inviati dai tecnici.
    - **Carica Report**: Avvia una nuova sessione di validazione con gli ultimi report non ancora processati.
    - **Sessione Persistente**: La sessione rimane attiva anche se chiudi o aggiorni la pagina.
    - **Modifica Live**: Puoi modificare i dati direttamente nella tabella. Ogni modifica viene salvata automaticamente.
    - **Valida e Salva**: Invia le modifiche finali al database e chiude la sessione.
    - **Cancella**: Annulla la sessione corrente, eliminando tutte le modifiche non salvate.
    """)

    # 1. Controlla se esiste una sessione di validazione attiva per l'utente
    active_session = get_active_validation_session(user_matricola)

    if active_session:
        st.markdown("---")
        st.subheader("📝 Sessione di Validazione in Corso")

        session_id = active_session["session_id"]
        report_data = active_session["data"]

        # Usa un DataFrame per st.data_editor
        # Inizializza o aggiorna il DataFrame in session_state solo se necessario
        if 'validation_df' not in st.session_state or st.session_state.get('validation_session_id') != session_id:
             st.session_state.validation_df = pd.DataFrame(report_data)
             st.session_state.validation_session_id = session_id

        # L'editor dati
        edited_df = st.data_editor(
            st.session_state.validation_df,
            num_rows="dynamic",
            key=f"data_editor_{session_id}",
            use_container_width=True,
            column_config={
                "Report": st.column_config.TextColumn(width="large"),
                "Descrizione": st.column_config.TextColumn(width="medium"),
                "PdL": st.column_config.TextColumn(width="small"),
                "Tecnico": st.column_config.TextColumn(width="small"),
                "Stato": st.column_config.TextColumn(width="small"),
            },
            disabled=["PdL", "Descrizione", "Tecnico", "Data_Compilazione", "Matricola"]
        )

        # Salva le modifiche in tempo reale
        if not edited_df.equals(st.session_state.validation_df):
            update_validation_session_data(session_id, edited_df.to_dict('records'))
            st.session_state.validation_df = edited_df.copy() # Aggiorna lo stato base
            st.toast("Modifiche salvate nella sessione.")

        st.markdown("---")

        # Pulsanti di azione
        col1, col2, col3 = st.columns([2, 2, 5])
        with col1:
            if st.button("✅ Valida e Salva Modifiche", type="primary", width='stretch'):
                with st.spinner("Salvataggio dei report validati in corso..."):
                    if process_and_commit_validated_reports(edited_df.to_dict('records')):
                        delete_validation_session(session_id)
                        st.success("Report validati e salvati con successo!")
                        # Pulisci lo stato per forzare il ricaricamento
                        if 'validation_df' in st.session_state: del st.session_state.validation_df
                        if 'validation_session_id' in st.session_state: del st.session_state.validation_session_id
                        st.rerun()
                    else:
                        st.error("Si è verificato un errore durante il salvataggio dei report.")

        with col2:
            if st.button("❌ Cancella Sessione", width='stretch'):
                if delete_validation_session(session_id):
                    st.info("Sessione di validazione cancellata.")
                    # Pulisci lo stato
                    if 'validation_df' in st.session_state: del st.session_state.validation_df
                    if 'validation_session_id' in st.session_state: del st.session_state.validation_session_id
                    st.rerun()
                else:
                    st.error("Errore durante la cancellazione della sessione.")
    else:
        # Se non c'è una sessione attiva, mostra il pulsante per crearne una
        st.markdown("---")
        if st.button("📥 Carica Report da Validare", type="primary"):
            unvalidated_reports = get_unvalidated_reports()
            if unvalidated_reports:
                session_id = create_validation_session(user_matricola, unvalidated_reports)
                if session_id:
                    st.success(f"Creati {len(unvalidated_reports)} report da validare. La sessione è iniziata.")
                    st.rerun()
                else:
                    st.error("Impossibile creare una sessione di validazione.")
            else:
                st.success("🎉 Nessun nuovo report da validare al momento.")

def render_reperibilita_tab(gestionale_data, matricola_utente, ruolo_utente):
    st.subheader("📅 Calendario Reperibilità Settimanale")

    # --- DATI E CONFIGURAZIONE ---
    HOLIDAYS_2025 = [
        datetime.date(2025, 1, 1), datetime.date(2025, 1, 6), datetime.date(2025, 4, 20),
        datetime.date(2025, 4, 21), datetime.date(2025, 4, 25), datetime.date(2025, 5, 1),
        datetime.date(2025, 6, 2), datetime.date(2025, 8, 15), datetime.date(2025, 11, 1),
        datetime.date(2025, 12, 8), datetime.date(2025, 12, 25), datetime.date(2025, 12, 26),
    ]
    WEEKDAY_NAMES_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    MESI_ITALIANI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    today = datetime.date.today()

    # --- GESTIONE MODALE PRIMA DI TUTTO ---
    # Se siamo in modalità "gestione", mostriamo solo l'interfaccia di gestione e fermiamo il resto.
    if 'managing_oncall_shift_id' in st.session_state and st.session_state.managing_oncall_shift_id:
        shift_id_to_manage = st.session_state.managing_oncall_shift_id
        matricola_to_manage = st.session_state.managing_oncall_user_matricola

        df_contatti = gestionale_data['contatti']
        user_to_manage_name = df_contatti[df_contatti['Matricola'] == matricola_to_manage].iloc[0]['Nome Cognome']

        with st.container(border=True):
            st.subheader("Gestione Turno di Reperibilità")
            try:
                turno_info = gestionale_data['turni'][gestionale_data['turni']['ID_Turno'] == shift_id_to_manage].iloc[0]
                st.write(f"Stai modificando il turno di **{user_to_manage_name}** per il giorno **{pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')}**.")
            except IndexError:
                st.error("Dettagli del turno non trovati.")
                # Aggiungiamo un pulsante per uscire in caso di errore
                if st.button("⬅️ Torna al Calendario"):
                     if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                     st.rerun()
                st.stop()


            if st.session_state.get('oncall_swap_mode'):
                st.markdown("**A chi vuoi chiedere il cambio?**")
                contatti_validi = df_contatti[
                    (df_contatti['Matricola'] != matricola_to_manage) &
                    (df_contatti['PasswordHash'].notna())
                ]

                matricola_to_name = pd.Series(contatti_validi['Nome Cognome'].values, index=contatti_validi['Matricola']).to_dict()
                ricevente_matricola = st.selectbox("Seleziona collega:", contatti_validi['Matricola'].tolist(), format_func=lambda m: matricola_to_name.get(m, m), key=f"swap_select_{shift_id_to_manage}")


                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Invia Richiesta", key=f"swap_confirm_{shift_id_to_manage}", width='stretch', type="primary"):
                        if richiedi_sostituzione_logic(gestionale_data, matricola_to_manage, ricevente_matricola, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                            st.rerun()
                with c2:
                    if st.button("Annulla Scambio", width='stretch'):
                        del st.session_state.oncall_swap_mode
                        st.rerun()
            else:
                st.info("Cosa vuoi fare con questo turno?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📢 Pubblica in Bacheca", width='stretch'):
                        if pubblica_turno_in_bacheca_logic(gestionale_data, matricola_to_manage, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            st.rerun()
                with col2:
                    if st.button("🔄 Chiedi Sostituzione", width='stretch'):
                        st.session_state.oncall_swap_mode = True
                        st.rerun()

            st.divider()
            if st.button("⬅️ Torna al Calendario", key=f"cancel_manage_{shift_id_to_manage}", width='stretch'):
                if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                if 'managing_oncall_user_matricola' in st.session_state: del st.session_state.managing_oncall_user_matricola
                if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                st.rerun()
        st.stop() # Ferma l'esecuzione per non mostrare il calendario sotto la modale

    # --- STATO DELLA SESSIONE ---
    if 'week_start_date' not in st.session_state:
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())

    # --- LOGICA DI NAVIGAZIONE ---
    current_year = st.session_state.week_start_date.year
    selected_month = st.selectbox(
        "Mese", range(1, 13),
        format_func=lambda m: MESI_ITALIANI[m-1],
        index=st.session_state.week_start_date.month - 1,
        key="month_select"
    )
    selected_year = st.selectbox(
        "Anno", range(2024, 2027),
        index=current_year - 2024,
        key="year_select"
    )

    if selected_year != st.session_state.week_start_date.year or selected_month != st.session_state.week_start_date.month:
        new_date = datetime.date(selected_year, selected_month, 1)
        st.session_state.week_start_date = new_date - datetime.timedelta(days=new_date.weekday())
        st.rerun()

    col_nav1, col_nav2, col_nav3 = st.columns([1, 5, 1])
    with col_nav1:
        if st.button("⬅️", help="Settimana precedente", width='stretch'):
            st.session_state.week_start_date -= datetime.timedelta(weeks=1)
            st.rerun()
    with col_nav2:
        week_start = st.session_state.week_start_date
        week_end = week_start + datetime.timedelta(days=6)
        week_label = f"{week_start.strftime('%d')} {MESI_ITALIANI[week_start.month-1]}"
        if week_start.year != week_end.year:
            week_label += f" {week_start.year} — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        elif week_start.month != week_end.month:
            week_label += f" — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        else:
            week_label += f" — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        st.markdown(f"<div style='text-align: center; font-weight: bold; margin-top: 8px;'>{week_label}</div>", unsafe_allow_html=True)
    with col_nav3:
        if st.button("➡️", help="Settimana successiva", width='stretch'):
            st.session_state.week_start_date += datetime.timedelta(weeks=1)
            st.rerun()

    if st.button("Vai a Oggi", width='stretch'):
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())
        st.rerun()

    st.divider()

    # --- RECUPERO DATI REPERIBILITÀ ---
    df_turni = gestionale_data['turni']
    df_prenotazioni = gestionale_data['prenotazioni']
    oncall_shifts_df = df_turni[df_turni['Tipo'] == 'Reperibilità'].copy()
    oncall_shifts_df['Data'] = pd.to_datetime(oncall_shifts_df['Data'])
    oncall_shifts_df['date_only'] = oncall_shifts_df['Data'].dt.date

    # --- VISUALIZZAZIONE CALENDARIO ---
    week_dates = [st.session_state.week_start_date + datetime.timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for i, day in enumerate(week_dates):
        with cols[i]:
            is_today = (day == today)
            is_weekend = day.weekday() in [5, 6]
            is_holiday = day in HOLIDAYS_2025

            border_style = "2px solid #007bff" if is_today else "1px solid #d3d3d3"
            day_color = "red" if is_holiday else "inherit"

            if is_today:
                background_color = "#e0f7fa"
            elif is_weekend:
                background_color = "#fff0f0"
            else:
                background_color = "white"

            technicians_html = ""
            shift_today = oncall_shifts_df[oncall_shifts_df['date_only'] == day]
            user_is_on_call = False
            shift_id_today = None
            managed_user_matricola = matricola_utente

            if not shift_today.empty:
                shift_id_today = shift_today.iloc[0]['ID_Turno']
                prenotazioni_today = df_prenotazioni[df_prenotazioni['ID_Turno'] == shift_id_today]
                df_contatti = gestionale_data.get('contatti', pd.DataFrame())
                matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola'].astype(str)).to_dict()


                if not prenotazioni_today.empty:
                    tech_display_list = []
                    for _, booking in prenotazioni_today.iterrows():
                        technician_matricola = str(booking['Matricola'])
                        technician_name = matricola_to_name.get(technician_matricola, f"Matricola {technician_matricola}")
                        surname = technician_name.split()[-1].upper()

                        user_details = df_contatti[df_contatti['Matricola'] == technician_matricola]
                        is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('PasswordHash'))

                        display_name = f"<i>{surname} (Esterno)</i>" if is_placeholder else surname
                        tech_display_list.append(display_name)

                        if technician_matricola == str(matricola_utente):
                            user_is_on_call = True

                    if tech_display_list:
                        managed_user_matricola = str(prenotazioni_today.iloc[0]['Matricola'])

                    technicians_html = "".join([f"<div style='font-size: 0.9em; font-weight: 500; line-height: 1.3; margin-bottom: 2px;'>{s}</div>" for s in tech_display_list])
                else:
                    technicians_html = "<span style='color: grey; font-style: italic;'>Libero</span>"
            else:
                 technicians_html = "<span style='color: grey; font-style: italic;'>N/D</span>"

            st.markdown(
                f"""
                <div style="border: {border_style}; border-radius: 8px; padding: 8px; background-color: {background_color}; height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%;">
                        <!-- Colonna Sinistra: Giorno -->
                        <div style="text-align: left;">
                            <p style="font-weight: bold; color: {day_color}; margin: 0; font-size: 0.9em;">{WEEKDAY_NAMES_IT[day.weekday()]}</p>
                            <h3 style="margin: 0; color: {day_color};">{day.day}</h3>
                        </div>
                        <!-- Colonna Destra: Tecnici -->
                        <div style="text-align: right; padding-left: 5px;">
                            {technicians_html}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True
            )

            can_manage = (user_is_on_call or ruolo_utente == "Amministratore") and shift_id_today
            if can_manage:
                if st.button("Gestisci", key=f"manage_{day}", width='stretch'):
                    st.session_state.managing_oncall_shift_id = shift_id_today
                    st.session_state.managing_oncall_user_matricola = managed_user_matricola
                    st.rerun()


def render_situazione_impianti_tab():
    st.header("Controllo Generale Attività")
    st.info("Questa sezione fornisce una visione aggregata dello stato di avanzamento di tutte le attività programmate.")

    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Nessun dato sulle attività programmate trovato nel database.")
        return

    # Raggruppa gli stati "DA CHIUDERE" e "SCADUTO" in "TERMINATA"
    df['STATO_PdL'] = df['STATO_PdL'].replace(['DA CHIUDERE', 'SCADUTO'], 'TERMINATA')


    # --- Filtri ---
    st.subheader("Filtra Dati")

    # Ora c'è solo un filtro per Area
    aree_disponibili = sorted(df['AREA'].dropna().unique()) if 'AREA' in df.columns else []
    default_aree = aree_disponibili
    aree_selezionate = st.multiselect("Filtra per Area", options=aree_disponibili, default=default_aree, key="area_filter_situazione")

    # Il filtro per stato non è più necessario come prima, ma lo usiamo internamente
    # per separare le terminate dalle altre per il grafico
    # stati_disponibili = sorted(df['STATO_PdL'].dropna().unique())

    # Applica filtro per area
    filtered_df = df.copy()
    if aree_selezionate:
        filtered_df = filtered_df[filtered_df['AREA'].isin(aree_selezionate)]

    st.divider()

    if filtered_df.empty:
        st.info("Nessuna attività corrisponde ai filtri selezionati.")
        return

    # --- Metriche ---
    st.subheader("Metriche di Riepilogo")
    total_activities = len(filtered_df)
    # La metrica delle completate ora conta solo 'TERMINATA'
    completed_activities = len(filtered_df[filtered_df['STATO_PdL'] == "TERMINATA"])
    pending_activities = total_activities - completed_activities

    c1, c2, c3 = st.columns(3)
    c1.metric("Totale Attività", total_activities)
    c2.metric("Attività Terminate", completed_activities) # Etichetta cambiata
    c3.metric("Attività da Completare", pending_activities)

    # --- Grafici ---
    st.subheader("Visualizzazione Dati")

    st.markdown("#### Attività per Area e Stato")
    if 'AREA' in filtered_df.columns and 'STATO_PdL' in filtered_df.columns:
        # Crea un pivot table per avere il conteggio per Area e Stato
        status_pivot = filtered_df.groupby(['AREA', 'STATO_PdL']).size().unstack(fill_value=0)

        # Assicurati che le colonne desiderate esistano
        if 'TERMINATA' not in status_pivot.columns:
            status_pivot['TERMINATA'] = 0

        # Riorganizza le colonne per avere un ordine consistente se necessario
        # Esempio: status_pivot = status_pivot[['IN CORSO', 'SOSPESA', 'TERMINATA']]

        if not status_pivot.empty:
            # Prepara i dati per Vega-Lite (formato lungo)
            chart_data = status_pivot.reset_index().melt(
                id_vars='AREA',
                var_name='STATO_PdL',
                value_name='Numero di Attività'
            )

            # Specifica Vega-Lite per un grafico a barre impilate senza zoom
            vega_spec = {
                "width": "container",
                "mark": "bar",
                "encoding": {
                    "x": {"field": "AREA", "type": "nominal", "axis": {"title": "Area"}},
                    "y": {"field": "Numero di Attività", "type": "quantitative", "axis": {"title": "Numero di Attività"}},
                    "color": {"field": "STATO_PdL", "type": "nominal", "title": "Stato"},
                    "tooltip": [
                        {"field": "AREA", "type": "nominal"},
                        {"field": "STATO_PdL", "type": "nominal"},
                        {"field": "Numero di Attività", "type": "quantitative"}
                    ]
                },
                "params": []
            }
            st.vega_lite_chart(chart_data, vega_spec, use_container_width=True)
        else:
            st.info("Nessun dato per il grafico.")
    else:
        st.info("Colonne 'AREA' o 'STATO_PdL' non trovate.")


    st.divider()

    # --- Tabella Dati ---
    st.subheader("Dettaglio Attività Filtrate")
    st.dataframe(filtered_df)


def render_programmazione_tab():
    st.header("Pianificazione Dettagliata Attività")
    st.info("Consulta il dettaglio delle singole attività programmate, filtra per trovare attività specifiche e visualizza lo storico degli interventi.")

    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Nessun dato sulle attività programmate trovato nel database.")
        return

    # --- Filtri ---
    st.subheader("Filtra Attività")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdl_search = st.text_input("Cerca per PdL")

    with col2:
        aree_disponibili = sorted(df['AREA'].dropna().unique()) if 'AREA' in df.columns else []
        area_selezionata = st.multiselect("Filtra per Area", options=aree_disponibili, default=aree_disponibili, key="area_filter_programmazione")

    with col3:
        giorni_settimana = ["LUN", "MAR", "MER", "GIO", "VEN"]
        giorni_selezionati = st.multiselect("Filtra per Giorno", options=giorni_settimana, default=giorni_settimana)

    # Applica filtri
    filtered_df = df.copy()
    if pdl_search:
        filtered_df = filtered_df[filtered_df['PdL'].astype(str).str.contains(pdl_search, case=False, na=False)]
    if area_selezionata:
        filtered_df = filtered_df[filtered_df['AREA'].isin(area_selezionata)]
    if giorni_selezionati:
        mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
        for giorno in giorni_selezionati:
            if giorno in filtered_df.columns:
                mask |= (filtered_df[giorno].str.lower() == 'x')
        filtered_df = filtered_df[mask]

    st.divider()

    if filtered_df.empty:
        st.info("Nessuna attività corrisponde ai filtri selezionati.")
        return

    # --- Grafico Carico di Lavoro ---
    st.subheader("Carico di Lavoro Settimanale per Area")
    giorni_settimana = ["LUN", "MAR", "MER", "GIO", "VEN"]

    # Prepara i dati per il grafico
    chart_data = []
    for giorno in giorni_settimana:
        if giorno in filtered_df.columns:
            # Filtra le attività per il giorno corrente
            day_activities = filtered_df[filtered_df[giorno].str.lower() == 'x']
            if not day_activities.empty:
                # Conta le attività per area in quel giorno
                area_counts_for_day = day_activities['AREA'].value_counts().to_dict()
                for area, count in area_counts_for_day.items():
                    chart_data.append({'Giorno': giorno, 'Area': area, 'Numero di Attività': count})

    if not chart_data:
        st.info("Nessun dato disponibile per visualizzare il carico di lavoro settimanale.")
    else:
        # Crea un DataFrame e pivottalo per il formato corretto del grafico
        chart_df = pd.DataFrame(chart_data)
        pivot_df = chart_df.pivot(index='Giorno', columns='Area', values='Numero di Attività').fillna(0)

        # Assicura l'ordine corretto dei giorni da LUN a VEN
        pivot_df = pivot_df.reindex(giorni_settimana).fillna(0)

        # Prepara i dati per Vega-Lite
        chart_data = pivot_df.reset_index().melt(
            id_vars='Giorno',
            var_name='Area',
            value_name='Numero di Attività'
        )

        # Specifica Vega-Lite
        vega_spec = {
            "width": "container",
            "mark": "bar",
            "encoding": {
                "x": {"field": "Giorno", "type": "ordinal", "sort": giorni_settimana, "axis": {"title": "Giorno della Settimana"}},
                "y": {"field": "Numero di Attività", "type": "quantitative", "axis": {"title": "Numero di Attività"}},
                "color": {"field": "Area", "type": "nominal", "title": "Area"},
                "tooltip": [
                    {"field": "Giorno", "type": "nominal"},
                    {"field": "Area", "type": "nominal"},
                    {"field": "Numero di Attività", "type": "quantitative"}
                ]
            },
            "params": []
        }
        st.vega_lite_chart(chart_data, vega_spec, use_container_width=True)

    st.divider()

    # --- Dettaglio Attività (Card) ---
    st.subheader("Dettaglio Attività")
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            pdl = row.get('PdL', 'N/D')
            descrizione = row.get('DESCRIZIONE_ATTIVITA', 'N/D')
            area = row.get('AREA', 'N/D')
            stato = row.get('STATO_ATTIVITA', 'N/D')

            # Trova i giorni in cui l'attività è programmata
            giorni_programmati = [giorno for giorno in giorni_settimana if str(row.get(giorno, '')).lower() == 'x']
            giorni_str = ", ".join(giorni_programmati) if giorni_programmati else "Non specificato"

            st.markdown(f"**PdL `{pdl}`** - {descrizione}")
            st.caption(f"Area: {area} | Stato: {stato} | Giorno/i: **{giorni_str}**")

            # Storico
            storico_list = row.get('Storico', [])
            if storico_list:
                visualizza_storico_organizzato(storico_list, pdl)
            else:
                st.markdown("*Nessuno storico disponibile per questo PdL.*")


# La funzione render_update_reports_tab è stata integrata direttamente
# nella dashboard dell'amministratore per una maggiore chiarezza e per
# riflettere il nuovo flusso di dati bidirezionale.
# La logica ora risiede nella scheda "Gestione Dati" della "Dashboard Caposquadra".

def render_access_logs_tab(gestionale_data):
    st.header("Cronologia Accessi al Sistema")
    st.info("Questa sezione mostra tutti i tentativi di accesso registrati, dal più recente al più vecchio.")

    logs_df = gestionale_data.get('access_logs')

    # La nuova funzione carica un DataFrame, quindi il controllo va fatto con .empty
    if logs_df is None or logs_df.empty:
        st.warning("Nessun tentativo di accesso registrato.")
        return

    # Non è più necessario convertire in DataFrame, lo è già.
    # Assicuriamoci solo che la colonna timestamp sia nel formato corretto
    if 'timestamp' in logs_df.columns:
        logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
        logs_df = logs_df.sort_values(by='timestamp', ascending=False)

    # --- Filtri ---
    st.subheader("Filtra Cronologia")

    # Filtro per utente
    all_users = sorted(logs_df['username'].unique().tolist())
    selected_users = st.multiselect(
        "Filtra per Utente:",
        options=all_users,
        default=[]
    )

    # Filtro per data
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data Inizio", value=None)
    with col2:
        end_date = st.date_input("Data Fine", value=None)

    # Applica i filtri
    filtered_df = logs_df.copy()
    if selected_users:
        filtered_df = filtered_df[filtered_df['username'].isin(selected_users)]

    if start_date:
        filtered_df = filtered_df[filtered_df['timestamp'].dt.date >= start_date]

    if end_date:
        filtered_df = filtered_df[filtered_df['timestamp'].dt.date <= end_date]

    st.divider()

    # --- Visualizzazione ---
    st.subheader("Risultati")

    if filtered_df.empty:
        st.info("Nessun record trovato per i filtri selezionati.")
    else:
        # Formattazione per la visualizzazione
        display_df = filtered_df.copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%d/%m/%Y %H:%M:%S')
        display_df.rename(columns={
            'timestamp': 'Data e Ora',
            'username': 'Nome Utente/Matricola',
            'status': 'Esito'
        }, inplace=True)

        st.dataframe(display_df[['Data e Ora', 'Nome Utente/Matricola', 'Esito']], use_container_width=True)


def render_guida_tab(ruolo):
    st.title("❓ Guida del Gestionale")
    st.write("Benvenuto nella guida utente! Qui troverai le istruzioni per usare al meglio l'applicazione.")
    st.info("Usa i menù a tendina qui sotto per esplorare le diverse sezioni e funzionalità dell'app. La tua sessione ora rimane attiva anche se aggiorni la pagina!")

    # Sezione Attività Assegnate
    with st.expander("📝 Attività Assegnate", expanded=True):
        st.markdown("""
        Questa è la sezione principale per la gestione delle tue attività quotidiane. È suddivisa in due sotto-schede:

        - **Attività di Oggi**: Mostra l'elenco delle attività che ti sono state assegnate per la giornata corrente.
        - **Attività Giorno Precedente**: Permette di recuperare e compilare eventuali attività non completate del giorno lavorativo precedente.

        #### Come compilare un report
        Per ogni attività in entrambe le schede, il processo è identico:
        - Vedrai il codice **PdL** e una breve descrizione.
        - Se lavori in **Team**, vedrai i nomi dei tuoi colleghi, il loro ruolo e gli orari di lavoro per quell'attività.
        - Puoi scegliere tra due modalità di compilazione:
            - **✍️ Compila Report Guidato (IA)**: Una procedura a domande che ti aiuta a scrivere un report completo e standardizzato.
            - **📝 Compila Report Manuale**: Un campo di testo libero dove puoi scrivere il report come preferisci.
        - **Importante per gli Aiutanti**: Se fai parte di un team con più persone, solo un **Tecnico** può compilare il report. Potrai vedere l'attività e il report una volta compilato, ma non potrai inviarlo. Se lavori da solo, puoi compilare il report normalmente.

        #### Vedere lo Storico
        Sotto ogni attività, puoi espandere la sezione `"Mostra cronologia interventi"` per vedere tutti i report passati relativi a quel PdL. Questo è utile per capire i problemi ricorrenti.

        #### Compilare una Relazione di Reperibilità
        Se sei un **Tecnico** o **Amministratore**, vedrai una terza sotto-scheda chiamata **"Compila Relazione"**. Questa sezione serve per scrivere relazioni dettagliate, ad esempio per i turni di reperibilità.
        - **Data e Ora**: Inserisci la data (obbligatoria) e gli orari di inizio/fine del tuo intervento. Se non ricordi l'orario, puoi lasciare i campi vuoti.
        - **Partner**: Se hai lavorato con un collega, puoi selezionarlo dall'elenco a tendina.
        - **Corpo della Relazione**: Scrivi qui il testo del tuo report.
        - **Correzione con IA**: Una volta scritto il testo, puoi cliccare su **"Correggi con IA"**. Il sistema analizzerà il tuo testo e ti proporrà una versione migliorata, più professionale e senza errori, basandosi sullo stile di centinaia di altre relazioni.
        - **Usa Testo Corretto**: Dopo la correzione, apparirà il testo suggerito dall'IA e un pulsante **"Usa Testo Corretto"**. Cliccalo per copiare la versione dell'IA nel campo di testo principale.
        - **Invia Relazione**: Quando sei soddisfatto, clicca su **"Invia Relazione"** per mandare il report finale via email.
        """)

    with st.expander("📊 Pianificazione e Controllo"):
        st.subheader("Monitorare e Pianificare le Attività")
        st.markdown("""
        Questa sezione è il tuo centro di comando per la visione d'insieme delle attività. È divisa in due sottomenù:

        #### 1. Controllo
        - **Obiettivo**: Fornire una **visione aggregata** dello stato di avanzamento di tutte le attività.
        - **Come funziona**: Unisce i dati della pianificazione con i report compilati, dando sempre la priorità allo stato più aggiornato. Puoi vedere grafici e metriche generali.
        - **Uso**: Ideale per capire rapidamente quali aree o TCL hanno più attività in sospeso, completate o in corso.
        - **Filtri**: Puoi filtrare i dati per **TCL**, **Area** e **Stato** per analisi più mirate. Clicca su **"Applica Filtri"** per aggiornare la vista.

        #### 2. Pianificazione
        - **Obiettivo**: Consultare il **dettaglio delle singole attività** programmate per la settimana.
        - **Come funziona**: Mostra una lista di "card", una per ogni attività, con tutti i dettagli operativi (PdL, impianto, descrizione).
        - **Caratteristiche**:
            - **Storico Integrato**: Puoi espandere lo storico degli interventi direttamente dalla card dell'attività.
            - **Grafico Carico di Lavoro**: Un grafico a barre ti mostra il carico di lavoro giornaliero suddiviso per area.
            - **Filtri Dettagliati**: Puoi cercare attività specifiche per **PdL**, **Area**, **TCL** o **Giorno** della settimana.
        """)

    # Sezione Turni (unificata)
    with st.expander("📅 Gestione Turni (Assistenza, Straordinari, Reperibilità)"):
        st.subheader("Prenotare un Turno di Assistenza o Straordinario")
        st.markdown("""
        Nella sotto-sezione `📅 Turni`, puoi vedere tutti i turni di assistenza o straordinario a cui puoi partecipare.
        1.  Trova un turno con posti liberi (indicato da ✅).
        2.  Seleziona il ruolo che vuoi occupare ("Tecnico" o "Aiutante").
        3.  Clicca su **"Conferma Prenotazione"**.
        """)

        st.subheader("Gestire un Turno di Reperibilità")
        st.markdown("""
        Nella sotto-sezione `🗓️ Turni Reperibilità`, puoi visualizzare il calendario settimanale.
        - Se sei di turno in un determinato giorno, vedrai apparire il pulsante **"Gestisci"**.
        - Dato che i turni di reperibilità sono assegnati d'ufficio, l'unica azione disponibile è **"📢 Pubblica in Bacheca"**.
        - Cliccando questo pulsante, il tuo posto nel turno di reperibilità viene messo a disposizione di tutti i colleghi, che potranno prenderlo dalla sezione `📢 Bacheca`.
        """)

        st.subheader("Cedere un Turno (Assistenza/Straordinario): Le 3 Opzioni")
        st.markdown("Se sei già prenotato per un turno e non puoi più partecipare, hai 3 opzioni:")
        st.markdown("""
        1.  **Cancella Prenotazione**: L'opzione più semplice. La tua prenotazione viene rimossa e il posto torna disponibile per tutti. Usala se non hai bisogno di essere sostituito.
        2.  **📢 Pubblica in Bacheca**: Questa è l'opzione migliore se vuoi che qualcun altro prenda il tuo posto. Il tuo turno viene messo in una "bacheca" pubblica visibile a tutti. Il primo collega idoneo che lo accetta prenderà automaticamente il tuo posto e tu riceverai una notifica di conferma.
        3.  **🔄 Chiedi Sostituzione**: Usala se vuoi chiedere a un collega specifico di sostituirti. Seleziona il nome del collega e invia la richiesta. Riceverai una notifica se accetta o rifiuta.
        """)

        st.subheader("La Bacheca dei Turni (📢 Bacheca)")
        st.markdown("""
        Questa sotto-sezione è una bacheca pubblica dove trovi i turni che i tuoi colleghi (sia di assistenza/straordinario che di reperibilità) hanno messo a disposizione.
        - Se vedi un turno che ti interessa e hai il ruolo richiesto, puoi cliccare su **"Prendi questo turno"**.
        - La regola è: **"primo che arriva, primo servito"**. Se sarai il più veloce, il turno sarà tuo!
        - Il sistema aggiornerà automaticamente il calendario e invierà le notifiche di conferma.
        """)

    # Sezione Notifiche
    with st.expander("🔔 Notifiche"):
        st.subheader("Come Funzionano")
        st.markdown("""
        L'icona della campanella in alto a destra ti mostra se hai nuove notifiche. Un numero rosso indica i messaggi non letti.
        - Clicca sulla campanella per aprire il centro notifiche.
        - Riceverai notifiche per:
            - Nuovi turni disponibili.
            - Richieste di sostituzione ricevute.
            - Risposte alle tue richieste di sostituzione.
            - Conferme quando un tuo turno in bacheca viene preso da un collega.
        - Clicca sul pulsante **"letto"** per marcare una notifica come letta e farla sparire dal conteggio.
        """)

    with st.expander("🔐 Sicurezza Account e 2FA (Nuovo!)"):
        st.subheader("Impostare la Verifica in Due Passaggi (2FA)")
        st.markdown("""
        Per aumentare la sicurezza del tuo account, al primo accesso ti verrà chiesto di configurare la verifica in due passaggi.
        1.  **Installa un'app di Autenticazione**: Scarica sul tuo cellulare un'app come Google Authenticator, Microsoft Authenticator, o un'altra di tua scelta.
        2.  **Configura l'Account**:
            - **Da PC**: Apri l'app e scegli di scansionare il **QR Code** mostrato sullo schermo.
            - **Da Cellulare**: Clicca su **"Copia Codice"** e, nella tua app di autenticazione, scegli di inserire una "chiave di configurazione" manualmente.
        3.  **Verifica**: Inserisci il codice a 6 cifre generato dall'app per completare la configurazione.

        D'ora in poi, dopo aver inserito la password, dovrai inserire il codice temporaneo dalla tua app per accedere.
        """)
        st.subheader("Cosa fare se cambi cellulare?")
        st.warning("Se cambi cellulare o perdi accesso alla tua app di autenticazione, **contatta un amministratore**. Potrà resettare la tua configurazione 2FA e permetterti di registrarla sul nuovo dispositivo al tuo accesso successivo.")

    # Sezione Admin (visibile solo agli admin)
    if ruolo == "Amministratore":
        with st.expander("🔑 Funzionalità Amministratore"):
            st.subheader("Dashboard Admin Riorganizzata")
            st.markdown("""
            La `Dashboard Admin` è stata suddivisa in due aree principali per separare le funzionalità operative da quelle puramente tecniche:
            """)

            st.markdown("#### 1. Dashboard Caposquadra")
            st.markdown("""
            Questa sezione contiene gli strumenti per la gestione quotidiana del team e delle attività:
            - **Performance Team**: Analizza le metriche di performance dei tecnici.
            - **Crea Nuovo Turno**: Permette di creare nuovi turni di assistenza o straordinario.
            - **Aggiorna Report**: Sincronizza manualmente i report da Google Sheets, li visualizza e permette di modificarli e salvarli.
            """)

            st.markdown("#### 2. Dashboard Tecnica")
            st.markdown("""
            Questa sezione contiene gli strumenti per la gestione tecnica e la configurazione del sistema:
            - **Gestione Account**: Per modificare utenti, resettare password e gestire i ruoli.
            - **Cronologia Accessi**: Monitora tutti i tentativi di accesso al sistema.
            - **Gestione IA**: Contiene le sotto-sezioni per la revisione delle conoscenze e l'aggiornamento della memoria dell'IA.
            """)

    # Sezione Archivio
    # Sezione Richieste (Nuova)
    with st.expander("📋 Richieste"):
        st.subheader("Come Inviare Richieste")
        st.markdown("""
        Questa nuova sezione è dedicata all'invio di richieste di vario tipo. È divisa in due sottomenù:

        #### 1. Richiesta Materiali
        - Usa questa sezione per richiedere materiali di consumo o attrezzature necessarie per il tuo lavoro.
        - **Come funziona**:
            - Vai al sottomenù **Materiali**.
            - Scrivi un elenco dettagliato di ciò che ti serve nel campo di testo.
            - Clicca su **"Invia Richiesta Materiali"**.
        - **Storico**: Tutte le richieste inviate sono visibili a tutti nello storico in fondo alla pagina, per trasparenza e per evitare richieste duplicate.

        #### 2. Richiesta Assenze (Ferie/Permessi)
        - Usa questa sezione per inviare richieste di ferie o permessi (es. Legge 104).
        - **Come funziona**:
            - Vai al sottomenù **Assenze**.
            - Seleziona il **tipo di assenza**.
            - Imposta le **date di inizio e fine** del periodo di assenza.
            - Aggiungi eventuali **note** (opzionale).
            - Clicca su **"Invia Richiesta Assenza"**.
        - **Privacy e Visibilità**:
            - Tutti gli utenti possono inviare richieste.
            - **Solo gli Amministratori** possono vedere lo storico completo di tutte le richieste di assenza inviate. Per gli altri utenti, questa sezione rimane privata.
        """)

    with st.expander("🗂️ Ricerca nell'Archivio"):
        st.subheader("Trovare Vecchi Report")
        st.markdown("Usa questa sezione per cercare tra tutti i report compilati in passato. Puoi filtrare per:")
        st.markdown("""
        - **PdL**: Per vedere tutti gli interventi su un punto specifico.
        - **Descrizione**: Per cercare parole chiave nell'attività.
        - **Tecnico**: Per vedere tutti i report compilati da uno o più colleghi.
        """)


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
def main_app(matricola_utente, ruolo):
    st.set_page_config(layout="wide", page_title="Gestionale")

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

    if st.session_state.get('editing_turno_id'):
        render_edit_shift_form(gestionale_data)
    elif st.session_state.get('debriefing_task'):
        knowledge_core = carica_knowledge_core()
        if knowledge_core:
            render_debriefing_ui(knowledge_core, matricola_utente, datetime.date.today())
    else:
        # Header con titolo, notifiche e pulsante di logout
        col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
        with col1:
            st.title(f"Gestionale")
            st.header(f"Ciao, {nome_utente_autenticato}!")
            st.caption(f"Ruolo: {ruolo}")
        with col2:
            st.write("") # Spacer
            st.write("") # Spacer
            user_notifications = leggi_notifiche(gestionale_data, matricola_utente)
            render_notification_center(user_notifications, gestionale_data, matricola_utente)
        with col3:
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

        oggi = datetime.date.today()
        
        # Carica i dati delle attività una sola volta
        dati_programmati_df = carica_dati_attivita_programmate()
        attivita_da_recuperare = []
        pdl_gia_recuperati = set()

        if ruolo in ["Amministratore", "Tecnico"]:
            stati_finali = {'Terminata', 'Completato', 'Annullato', 'Non Svolta'}
            status_dict = {}
            if not dati_programmati_df.empty:
                status_dict = dati_programmati_df.set_index('PdL')['STATO_ATTIVITA'].to_dict()

            pdl_compilati_sessione = {task['pdl'] for task in st.session_state.get("completed_tasks_yesterday", [])}

            for i in range(1, 8):
                giorno_controllo = oggi - datetime.timedelta(days=i)
                attivita_del_giorno = trova_attivita(matricola_utente, giorno_controllo.day, giorno_controllo.month, giorno_controllo.year, gestionale_data['contatti'])

                if attivita_del_giorno:
                    for task in attivita_del_giorno:
                        pdl = task['pdl']
                        if pdl in pdl_gia_recuperati or pdl in pdl_compilati_sessione:
                            continue

                        stato_attuale = status_dict.get(pdl, 'Pianificato')
                        if stato_attuale in stati_finali:
                            continue

                        # Logica Falsi Positivi Avanzata: controlla se esiste un intervento successivo o uguale
                        gia_rendicontato_dopo = any(
                            pd.to_datetime(interv.get('Data_Riferimento'), dayfirst=True, errors='coerce').date() >= giorno_controllo
                            for interv in task.get('storico', []) if pd.notna(pd.to_datetime(interv.get('Data_Riferimento'), dayfirst=True, errors='coerce'))
                        )
                        if gia_rendicontato_dopo:
                            continue

                        task['data_attivita'] = giorno_controllo
                        attivita_da_recuperare.append(task)
                        pdl_gia_recuperati.add(pdl)

            if attivita_da_recuperare:
                st.warning(f"**Promemoria:** Hai **{len(attivita_da_recuperare)} attività** degli ultimi 7 giorni non rendicontate.")

        main_tabs_list = ["Attività Assegnate", "Pianificazione e Controllo", "Database", "📅 Gestione Turni", "Richieste", "❓ Guida"]
        if ruolo == "Amministratore":
            main_tabs_list.append("Dashboard Admin")
        
        tabs = st.tabs(main_tabs_list)
        
        with tabs[0]:
            sub_tab_list = ["Attività di Oggi", "Recupero Attività Non rendicontate (Ultimi 7gg)"]
            if ruolo in ["Tecnico", "Amministratore"]:
                sub_tab_list.append("Compila Relazione")
            sub_tabs = st.tabs(sub_tab_list)

            with sub_tabs[0]:
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

            with sub_tabs[1]:
                st.header("Recupero Attività Non Rendicontate (Ultimi 7 Giorni)")
                disegna_sezione_attivita(attivita_da_recuperare, "yesterday", ruolo)

            # Contenuto per la nuova scheda "Compila Relazione"
            if ruolo in ["Tecnico", "Amministratore"] and len(sub_tabs) > 2:
                with sub_tabs[2]:
                    st.header("Compila Relazione di Reperibilità")

                    # Mostra il numero di documenti nella base di conoscenza
                    kb_count = get_report_knowledge_base_count()
                    if kb_count > 0:
                        st.caption(f"ℹ️ L'IA si basa su {kb_count} relazioni per la correzione.")
                    else:
                        st.caption("ℹ️ Base di conoscenza per l'IA non trovata o vuota.")

                    # Inizializza lo stato della sessione se non esiste
                    if 'relazione_testo' not in st.session_state:
                        st.session_state.relazione_testo = ""
                    if 'relazione_partner' not in st.session_state:
                        st.session_state.relazione_partner = None
                    if 'relazione_revisionata' not in st.session_state:
                        st.session_state.relazione_revisionata = ""
                    if 'technical_suggestions' not in st.session_state:
                        st.session_state.technical_suggestions = []

                    # Carica la lista dei contatti per il selettore del partner
                    contatti_df = gestionale_data.get('contatti', pd.DataFrame())
                    # Escludi l'utente corrente dalla lista dei partner selezionabili
                    lista_partner = contatti_df[contatti_df['Matricola'] != str(matricola_utente)]['Nome Cognome'].tolist()

                    with st.form("form_relazione"):
                        col_tech, col_partner = st.columns(2)
                        with col_tech:
                            st.text_input("Tecnico Compilatore", value=nome_utente_autenticato, disabled=True)
                        with col_partner:
                             partner_selezionato = st.selectbox(
                                "Seleziona Partner (opzionale)",
                                options=["Nessuno"] + sorted(lista_partner),
                                index=0
                            )

                        c1, c2, c3 = st.columns(3)
                        data_intervento = c1.date_input("Data Intervento*", help="Questo campo è obbligatorio.")
                        ora_inizio = c2.text_input("Ora Inizio")
                        ora_fine = c3.text_input("Ora Fine")

                        # Assegnazione della key per risolvere il bug del caching
                        st.session_state.relazione_testo = st.text_area("Corpo della Relazione", height=250, key="relazione_text_area", value=st.session_state.get('relazione_testo', ''))

                        # Pulsanti del form
                        b1, b2, b3 = st.columns(3)
                        submit_ai_button = b1.form_submit_button("🤖 Correggi con IA")
                        submit_suggestion_button = b2.form_submit_button("💡 Suggerimento Tecnico")
                        submit_save_button = b3.form_submit_button("✅ Invia Relazione", type="primary")

                    # Logica dopo la sottomissione del form
                    if submit_ai_button:
                        # Legge sempre il valore più aggiornato dallo stato della sessione
                        testo_da_revisionare = st.session_state.get('relazione_text_area', '')
                        st.session_state.relazione_testo = testo_da_revisionare # Sincronizza lo stato

                        if not testo_da_revisionare.strip():
                            st.warning("Per favore, scrivi il corpo della relazione prima di chiedere la correzione.")
                        elif not data_intervento:
                            st.error("Il campo 'Data Intervento' è obbligatorio.")
                        else:
                            with st.spinner("L'IA sta analizzando la relazione..."):
                                # La funzione di revisione ora gestisce autonomamente il recupero degli esempi
                                result = revisiona_relazione_con_ia(testo_da_revisionare, None) # Usa il testo più recente

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
                        # Legge sempre il valore più aggiornato dallo stato della sessione
                        testo_da_inviare = st.session_state.get('relazione_text_area', '')
                        if not data_intervento:
                            st.error("Il campo 'Data Intervento' è obbligatorio prima di inviare.")
                        elif not testo_da_inviare.strip():
                            st.error("Il corpo della relazione non può essere vuoto prima di inviare.")
                        else:
                            # Prepara e invia l'email
                            partner_text = f" in coppia con {partner_selezionato}" if partner_selezionato != "Nessuno" else ""
                            titolo_email = f"Relazione di Reperibilità del {data_intervento.strftime('%d/%m/%Y')} - {nome_utente_autenticato}"
                            html_body = f"""
                            <h3>Relazione di Reperibilità</h3>
                            <p><strong>Data:</strong> {data_intervento.strftime('%d/%m/%Y')}</p>
                            <p><strong>Tecnico:</strong> {nome_utente_autenticato}{partner_text}</p>
                            <p><strong>Orario:</strong> Da {ora_inizio or 'N/D'} a {ora_fine or 'N/D'}</p>
                            <hr>
                            <h4>Testo della Relazione:</h4>
                            <p>{testo_da_inviare.replace('\n', '<br>')}</p>
                            """
                            invia_email_con_outlook_async(titolo_email, html_body)
                            st.success("Relazione inviata con successo!")

                            # --- Logica di salvataggio per apprendimento continuo ---
                            try:
                                # Crea la cartella se non esiste
                                reports_dir = "relazioni_inviate"
                                os.makedirs(reports_dir, exist_ok=True)

                                # Crea un nome file univoco
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = os.path.join(reports_dir, f"relazione_{timestamp}.txt")

                                # Salva il contenuto della relazione
                                with open(filename, "w", encoding="utf-8") as f:
                                    f.write(testo_da_inviare)

                                st.toast("Relazione salvata per l'apprendimento futuro dell'IA.")

                            except Exception as e:
                                st.warning(f"Non è stato possibile salvare la relazione per l'IA: {e}")
                            # --- Fine logica di salvataggio ---

                            st.balloons()
                            # Svuota i campi dopo l'invio
                            st.session_state.relazione_testo = ""
                            st.session_state.relazione_revisionata = ""
                            st.session_state.technical_suggestions = []
                            st.rerun()


                    if st.session_state.get('relazione_revisionata'):
                        st.subheader("Testo corretto dall'IA")
                        st.info(st.session_state.relazione_revisionata)
                        if st.button("📝 Usa Testo Corretto"):
                            st.session_state.relazione_testo = st.session_state.relazione_revisionata
                            st.session_state.relazione_revisionata = "" # Pulisci dopo aver copiato
                            st.rerun()

                    if st.session_state.get('technical_suggestions'):
                        st.subheader("💡 Suggerimenti Tecnici")
                        for suggestion in st.session_state.get('technical_suggestions', []):
                            st.info(suggestion)


        # Scheda 1: Nuova sezione "Pianificazione e Controllo" con sotto-schede
        with tabs[1]:
            st.header("Pianificazione e Controllo")
            sub_tabs_pianificazione = st.tabs(["Controllo", "Pianificazione"])
            with sub_tabs_pianificazione[0]:
                render_situazione_impianti_tab()
            with sub_tabs_pianificazione[1]:
                render_programmazione_tab()

        # Scheda 2: Database (precedentemente "Ricerca nell'Archivio")
        with tabs[2]:
            from modules.db_manager import get_archive_filter_options, get_filtered_archived_activities
            st.subheader("Ricerca nel Database")

            # Carica le opzioni per i filtri in modo efficiente
            filter_options = get_archive_filter_options()

            # Inizializza le date in session_state se non presenti
            if 'db_start_date' not in st.session_state:
                st.session_state.db_start_date = None
            if 'db_end_date' not in st.session_state:
                st.session_state.db_end_date = None

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                pdl_search = st.text_input("Filtra per PdL", key="db_pdl_search")
            with c2:
                desc_search = st.text_input("Filtra per Descrizione", key="db_desc_search")
            with c3:
                imp_search = st.multiselect("Filtra per Impianto", options=filter_options['impianti'], key="db_imp_search")
            with c4:
                tec_search = st.multiselect("Filtra per Tecnico/i", options=filter_options['tecnici'], key="db_tec_search")

            st.divider()
            st.markdown("##### Filtra per Data Intervento")
            d1, d2, d3, d4 = st.columns([1,1,1,2])
            with d1:
                st.date_input("Da:", key="db_start_date", format="DD/MM/YYYY")
            with d2:
                st.date_input("A:", key="db_end_date", format="DD/MM/YYYY")
            with d3:
                if st.button("Ultimi 15 gg", key="db_last_15_days"):
                    st.session_state.db_end_date = datetime.date.today()
                    st.session_state.db_start_date = st.session_state.db_end_date - datetime.timedelta(days=15)
                    st.rerun()


            interventi_eseguiti_only = st.checkbox("Mostra solo interventi eseguiti", value=True, key="db_show_executed")
            st.divider()

            # Messaggio informativo per chiarire il comportamento della ricerca
            st.info("""
            **Nota:** La ricerca mostra per impostazione predefinita solo gli interventi con uno **storico compilato**.
            Per cercare anche le attività **pianificate ma non ancora eseguite**, deseleziona la casella "Mostra solo interventi eseguiti".
            """)

            # Esegui la ricerca se almeno un filtro è attivo o se è stato premuto il pulsante dei 15 giorni
            search_is_active = pdl_search or desc_search or imp_search or tec_search or (st.session_state.db_start_date and st.session_state.db_end_date)

            if search_is_active:
                with st.spinner("Ricerca in corso nel database..."):
                    risultati_df = get_filtered_archived_activities(
                        pdl_search, desc_search, imp_search, tec_search,
                        interventi_eseguiti_only,
                        st.session_state.db_start_date, st.session_state.db_end_date
                    )

                if risultati_df.empty:
                    st.info("Nessun record trovato per i filtri selezionati.")
                else:
                    st.info(f"Trovati {len(risultati_df)} PdL corrispondenti.")

                    # Usa st.session_state per la paginazione
                    ITEMS_PER_PAGE = 20
                    if 'db_search_page' not in st.session_state:
                        st.session_state.db_search_page = 0

                    start_idx = st.session_state.db_search_page * ITEMS_PER_PAGE
                    end_idx = start_idx + ITEMS_PER_PAGE

                    items_to_display_df = risultati_df.iloc[start_idx:end_idx]

                    for _, row in items_to_display_df.iterrows():
                        pdl = row['PdL']
                        impianto = row.get('IMP', 'N/D') # Usa .get per sicurezza
                        descrizione = row.get('DESCRIZIONE_ATTIVITA', 'N/D')
                        storico = row.get('Storico', [])

                        expander_title = f"PdL {pdl} | {impianto} | {str(descrizione)[:60]}..."
                        with st.expander(expander_title):
                            visualizza_storico_organizzato(storico, pdl)

                    # Logica di paginazione
                    total_results = len(risultati_df)
                    if end_idx < total_results:
                        st.divider()
                        if st.button("Carica Altri Risultati..."):
                            st.session_state.db_search_page += 1
                            st.rerun()
            else:
                st.info("Inserisci almeno un criterio per avviare la ricerca.")

        # Scheda 3: Gestione Turni (precedentemente indice 4)
        with tabs[3]:
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
                if turni_disponibili_bacheca.empty:
                    st.info("Al momento non ci sono turni liberi in bacheca.")
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
                                        if prendi_turno_da_bacheca_logic(gestionale_data, matricola_utente, ruolo, bacheca_entry['ID_Bacheca']):
                                            salva_gestionale_async(gestionale_data)
                                            st.rerun()
                                else:
                                    st.info("Non hai il ruolo richiesto per questo turno.")
                        except IndexError:
                            st.warning(f"Dettagli non trovati per il turno ID {bacheca_entry['ID_Turno']}. Potrebbe essere stato rimosso.")
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
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, True):
                                    salva_gestionale_async(gestionale_data); st.rerun()
                        with c2:
                            if st.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, False):
                                    salva_gestionale_async(gestionale_data); st.rerun()
                st.divider()
                st.markdown("#### 📤 Richieste Inviate")
                richieste_inviate = df_sostituzioni[df_sostituzioni['Richiedente_Matricola'] == str(matricola_utente)]
                if richieste_inviate.empty: st.info("Nessuna richiesta di sostituzione inviata.")
                for _, richiesta in richieste_inviate.iterrows():
                    ricevente_nome = matricola_to_name.get(str(richiesta['Ricevente_Matricola']), "Sconosciuto")
                    st.markdown(f"- Richiesta inviata a **{ricevente_nome}** per il turno **{richiesta['ID_Turno']}**.")

        # Scheda 4: Richieste
        with tabs[4]:
            st.header("Richieste")
            richieste_tabs = st.tabs(["Materiali", "Assenze"])

            # Sottomenù Materiali
            with richieste_tabs[0]:
                st.subheader("Richiesta Materiali")
                with st.form("form_richiesta_materiali", clear_on_submit=True):
                    dettagli_richiesta = st.text_area("Elenca qui i materiali necessari:", height=150)
                    submitted = st.form_submit_button("Invia Richiesta Materiali", type="primary")

                    if submitted:
                        if dettagli_richiesta.strip():
                            new_id = f"MAT_{int(datetime.datetime.now().timestamp())}"
                            df_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())

                            nuova_richiesta_data = {
                                'ID_Richiesta': new_id,
                                'Richiedente_Matricola': str(matricola_utente),
                                'Timestamp': datetime.datetime.now(),
                                'Stato': 'Inviata',
                                'Dettagli': dettagli_richiesta
                            }

                            # Assicura che la nuova riga abbia le stesse colonne del DataFrame di destinazione
                            # per prevenire problemi di disallineamento con pd.concat.
                            if not df_materiali.columns.empty:
                                nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data], columns=df_materiali.columns)
                            else:
                                nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data])

                            gestionale_data['richieste_materiali'] = pd.concat([df_materiali, nuova_richiesta_df], ignore_index=True)

                            if salva_gestionale_async(gestionale_data):
                                st.success("Richiesta materiali inviata con successo!")
                                # Invia email
                                titolo_email = f"Nuova Richiesta Materiali da {nome_utente_autenticato}"
                                html_body = f"""
                                <h3>Nuova Richiesta Materiali</h3>
                                <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                                <p><strong>Data e Ora:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                                <hr>
                                <h4>Materiali Richiesti:</h4>
                                <p>{dettagli_richiesta.replace('\n', '<br>')}</p>
                                """
                                invia_email_con_outlook_async(titolo_email, html_body)
                                st.rerun()
                            else:
                                st.error("Errore durante il salvataggio della richiesta.")
                        else:
                            st.warning("Il campo dei materiali non può essere vuoto.")

                st.divider()
                st.subheader("Storico Richieste Materiali")
                df_richieste_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())
                if df_richieste_materiali.empty:
                    st.info("Nessuna richiesta di materiali inviata.")
                else:
                    # Arricchisci lo storico con il nome del richiedente
                    df_contatti = gestionale_data.get('contatti', pd.DataFrame())
                    df_richieste_con_nome = pd.merge(
                        df_richieste_materiali,
                        df_contatti[['Matricola', 'Nome Cognome']],
                        left_on='Richiedente_Matricola',
                        right_on='Matricola',
                        how='left'
                    )
                    # Gestisci i casi in cui il nome non viene trovato
                    df_richieste_con_nome['Nome Cognome'] = df_richieste_con_nome['Nome Cognome'].fillna('Sconosciuto')

                    df_richieste_con_nome['Timestamp'] = pd.to_datetime(df_richieste_con_nome['Timestamp'])

                    # Seleziona e riordina le colonne per la visualizzazione
                    display_cols = ['Timestamp', 'Nome Cognome', 'Dettagli', 'Stato']
                    # Assicurati che tutte le colonne esistano prima di provare a visualizzarle
                    final_cols = [col for col in display_cols if col in df_richieste_con_nome.columns]

                    st.dataframe(df_richieste_con_nome[final_cols].sort_values(by="Timestamp", ascending=False), use_container_width=True)


            # Sottomenù Assenze
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
                            if data_inizio > data_fine:
                                st.error("La data di inizio non può essere successiva alla data di fine.")
                            else:
                                new_id = f"ASS_{int(datetime.datetime.now().timestamp())}"
                                nuova_richiesta_assenza = pd.DataFrame([{
                                    'ID_Richiesta': new_id,
                                    'Richiedente_Matricola': str(matricola_utente),
                                    'Timestamp': datetime.datetime.now(),
                                    'Tipo_Assenza': tipo_assenza,
                                    'Data_Inizio': pd.to_datetime(data_inizio),
                                    'Data_Fine': pd.to_datetime(data_fine),
                                    'Note': note_assenza,
                                    'Stato': 'Inviata'
                                }])

                                df_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
                                gestionale_data['richieste_assenze'] = pd.concat([df_assenze, nuova_richiesta_assenza], ignore_index=True)

                                if salva_gestionale_async(gestionale_data):
                                    st.success("Richiesta di assenza inviata con successo!")
                                    # Invia email
                                    titolo_email = f"Nuova Richiesta di Assenza da {nome_utente_autenticato}"
                                    html_body = f"""
                                    <h3>Nuova Richiesta di Assenza</h3>
                                    <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                                    <p><strong>Tipo:</strong> {tipo_assenza}</p>
                                    <p><strong>Periodo:</strong> dal {data_inizio.strftime('%d/%m/%Y')} al {data_fine.strftime('%d/%m/%Y')}</p>
                                    <hr>
                                    <h4>Note:</h4>
                                    <p>{note_assenza.replace('\n', '<br>') if note_assenza else 'Nessuna nota.'}</p>
                                    """
                                    invia_email_con_outlook_async(titolo_email, html_body)
                                    st.rerun()
                                else:
                                    st.error("Errore durante il salvataggio della richiesta.")
                        else:
                            st.warning("Le date di inizio e fine sono obbligatorie.")

                # Visualizzazione storico solo per admin
                if ruolo == "Amministratore":
                    st.divider()
                    st.subheader("Storico Richieste Assenze (Visibile solo agli Admin)")
                    df_richieste_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
                    if df_richieste_assenze.empty:
                        st.info("Nessuna richiesta di assenza inviata.")
                    else:
                        df_richieste_assenze['Timestamp'] = pd.to_datetime(df_richieste_assenze['Timestamp'])
                        df_richieste_assenze['Data_Inizio'] = pd.to_datetime(df_richieste_assenze['Data_Inizio']).dt.strftime('%d/%m/%Y')
                        df_richieste_assenze['Data_Fine'] = pd.to_datetime(df_richieste_assenze['Data_Fine']).dt.strftime('%d/%m/%Y')
                        st.dataframe(df_richieste_assenze.sort_values(by="Timestamp", ascending=False), use_container_width=True)


        # Scheda 5: Guida
        with tabs[5]:
            render_guida_tab(ruolo)

        if ruolo == "Amministratore":
            with tabs[6]: # Indice aggiornato per la dashboard admin
                st.subheader("Dashboard di Controllo")

                # Se è stata selezionata la vista di dettaglio, mostrala
                if st.session_state.get('detail_technician_matricola'):
                    render_technician_detail_view()
                else:
                    # Nuova struttura a due livelli per la dashboard admin
                    st.subheader("Dashboard di Controllo")
                    main_admin_tabs = st.tabs(["Dashboard Caposquadra", "Dashboard Tecnica"])

                    # --- Dashboard Caposquadra ---
                    with main_admin_tabs[0]:
                        caposquadra_tabs = st.tabs(["Performance Team", "Crea Nuovo Turno", "Gestione Dati", "Validazione Report"])

                        with caposquadra_tabs[0]: # Performance Team
                            st.markdown("#### Seleziona Intervallo Temporale")
                            if 'perf_start_date' not in st.session_state:
                                st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30)
                            if 'perf_end_date' not in st.session_state:
                                st.session_state.perf_end_date = datetime.date.today()

                            c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                            if c1.button("Oggi"): st.session_state.perf_start_date = st.session_state.perf_end_date = datetime.date.today()
                            if c2.button("Ultimi 7 giorni"): st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=7); st.session_state.perf_end_date = datetime.date.today()
                            if c3.button("Ultimi 30 giorni"): st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30); st.session_state.perf_end_date = datetime.date.today()

                            col1, col2 = st.columns(2)
                            with col1: st.date_input("Data di Inizio", key="perf_start_date", format="DD/MM/YYYY")
                            with col2: st.date_input("Data di Fine", key="perf_end_date", format="DD/MM/YYYY")

                            start_datetime, end_datetime = st.session_state.perf_start_date, st.session_state.perf_end_date

                            if st.button("📊 Calcola Performance", type="primary"):
                                with st.spinner("Calcolo delle performance in corso..."):
                                    performance_df = get_technician_performance_data(start_datetime, end_datetime)
                                st.session_state['performance_results'] = {'df': performance_df, 'start_date': pd.to_datetime(start_datetime), 'end_date': pd.to_datetime(end_datetime)}

                            if 'performance_results' in st.session_state and not st.session_state['performance_results']['df'].empty:
                                results = st.session_state['performance_results']
                                performance_df = results['df']
                                st.markdown("---")
                                st.markdown("### Riepilogo Performance del Team")

                                total_interventions_team = performance_df['Totale Interventi'].sum()
                                total_rushed_reports_team = performance_df['Report Sbrigativi'].sum()
                                # Calcolo ponderato del tasso di completamento
                                total_completed_interventions = (performance_df['Tasso Completamento (%)'].astype(float) / 100) * performance_df['Totale Interventi']
                                avg_completion_rate_team = (total_completed_interventions.sum() / total_interventions_team) * 100 if total_interventions_team > 0 else 0

                                st.download_button(label="📥 Esporta Riepilogo CSV", data=to_csv(performance_df), file_name='performance_team.csv', mime='text/csv')
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Totale Interventi", f"{total_interventions_team}")
                                c2.metric("Tasso Completamento Medio", f"{avg_completion_rate_team:.1f}%")
                                c3.metric("Report Sbrigativi", f"{total_rushed_reports_team}")

                                st.markdown("#### Dettaglio Performance per Tecnico")
                                for index, row in performance_df.iterrows():
                                    st.write(f"**Tecnico:** {index}")
                                    st.dataframe(row.to_frame().T)
                                    if st.button(f"Vedi Dettaglio Interventi di {index}", key=f"detail_{index}"):
                                        st.session_state.update({'detail_technician_matricola': row['Matricola'], 'detail_start_date': results['start_date'], 'detail_end_date': results['end_date']})
                                        st.rerun()

                        with caposquadra_tabs[1]: # Crea Nuovo Turno
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

                        with caposquadra_tabs[2]: # Gestione Dati
                            st.header("Gestione e Sincronizzazione Dati")
                            st.info("Usa questa sezione per gestire il flusso di dati tra il file Excel di pianificazione e il database dell'applicazione.")
                            st.divider()

                            # --- 1. Sincronizzazione da Excel a Database ---
                            st.subheader("1. Sincronizza Pianificazione da Excel")
                            st.warning(
                                "**Azione:** Copia i dati dal file `attivita_programmate.xlsm` al database.\n\n"
                                "**Uso:** Eseguire questa azione quando il file di pianificazione è stato aggiornato con nuove attività o programmazioni settimanali."
                            )
                            if st.button("🚀 Sincronizza Pianificazione da Excel", help="Sovrascrive la tabella delle attività nel DB con i dati del file Excel."):
                                from sincronizzatore import sincronizza_dati
                                with st.spinner("Sincronizzazione da Excel in corso..."):
                                    success, message = sincronizza_dati()
                                    if success:
                                        st.success(f"Sincronizzazione completata! {message}")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"Errore durante la sincronizzazione: {message}")

                            st.divider()

                            # --- 2. Consolidamento da Database a Excel ---
                            st.subheader("2. Consolida Report in Excel")
                            st.warning(
                                "**Azione:** Aggiorna il file `attivita_programmate.xlsm` con gli ultimi report compilati dai tecnici nel database.\n\n"
                                "**Uso:** Eseguire questa azione per salvare i progressi dal database al file master di pianificazione."
                            )
                            if st.button("⚙️ Consolida Report in Excel", help="Aggiorna il file Excel con i dati dei report presenti nel database."):
                                with st.spinner("Consolidamento dei report in Excel in corso..."):
                                    success, message = consolida_report_giornalieri()
                                    if success:
                                        st.success(message)
                                    else:
                                        st.error(message)

                        with caposquadra_tabs[3]: # Validazione Report
                            render_report_validation_tab(matricola_utente)

                    # --- Dashboard Tecnica ---
                    with main_admin_tabs[1]:
                        tecnica_tabs = st.tabs(["Gestione Account", "Cronologia Accessi", "Gestione IA"])

                        with tecnica_tabs[0]: # Gestione Account
                            render_gestione_account(gestionale_data)

                        with tecnica_tabs[1]: # Cronologia Accessi
                            render_access_logs_tab(gestionale_data)

                        with tecnica_tabs[2]: # Gestione IA
                            st.header("Gestione Intelligenza Artificiale")
                            ia_sub_tabs = st.tabs(["Revisione Conoscenze", "Memoria IA"])
                            with ia_sub_tabs[0]: # Revisione Conoscenze
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
                            with ia_sub_tabs[1]: # Memoria IA
                                st.subheader("Gestione Modello IA")
                                st.info("Usa questo pulsante per aggiornare la base di conoscenza dell'IA con le nuove relazioni inviate. L'operazione potrebbe richiedere alcuni minuti.")
                                if st.button("🧠 Aggiorna Memoria IA", type="primary"):
                                    with st.spinner("Ricostruzione dell'indice in corso..."):
                                        result = learning_module.build_knowledge_base()
                                    if result.get("success"): st.success(result.get("message")); st.cache_data.clear()
                                    else: st.error(result.get("message"))


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
                        # L'utente esiste ma non ha una password. La creiamo ora.
                        nome_completo, ruolo, password_fornita = user_data

                        # Hashing della nuova password
                        hashed_password = bcrypt.hashpw(password_fornita.encode('utf-8'), bcrypt.gensalt())

                        # Aggiornamento del DataFrame in memoria usando la matricola inserita
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