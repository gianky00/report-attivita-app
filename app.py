import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import re
import os
import json
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
    verify_2fa_code
)
from modules.data_manager import (
    carica_knowledge_core,
    carica_gestionale,
    salva_gestionale_async,
    carica_archivio_completo,
    trova_attivita,
    scrivi_o_aggiorna_risposta,
    carica_dati_attivita_programmate
)
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
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
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

def calculate_technician_performance(archivio_df, start_date, end_date):
    """Calcola le metriche di performance per i tecnici in un dato intervallo di tempo."""
    
    # Converte le date in formato datetime di pandas, gestendo errori
    archivio_df['Data_Riferimento_dt'] = pd.to_datetime(archivio_df['Data_Riferimento'], errors='coerce', dayfirst=True)
    # Estrae la data dalla colonna timestamp della compilazione
    archivio_df['Data_Compilazione_dt'] = pd.to_datetime(archivio_df['Data_Compilazione'], errors='coerce').dt.date
    archivio_df['Data_Compilazione_dt'] = pd.to_datetime(archivio_df['Data_Compilazione_dt']) # Riconverte a datetime64 per la sottrazione

    # Filtra il DataFrame per l'intervallo di date selezionato (basato sulla data di riferimento dell'attività)
    mask = (archivio_df['Data_Riferimento_dt'] >= start_date) & (archivio_df['Data_Riferimento_dt'] <= end_date)
    df_filtered = archivio_df[mask].copy()

    if df_filtered.empty:
        return pd.DataFrame()

    # Calcola il ritardo di compilazione in giorni
    # Assicura che entrambe le colonne siano datetime valide prima di sottrarre
    valid_dates = df_filtered.dropna(subset=['Data_Riferimento_dt', 'Data_Compilazione_dt'])
    valid_dates['Ritardo_Compilazione'] = (valid_dates['Data_Compilazione_dt'] - valid_dates['Data_Riferimento_dt']).dt.days
    
    # Raggruppa per tecnico
    performance_data = {}
    for tecnico, group in df_filtered.groupby('Tecnico'):
        # Filtra anche il gruppo con date valide per il calcolo del ritardo
        group_valid_dates = valid_dates[valid_dates['Tecnico'] == tecnico]

        total_interventions = len(group)
        completed_interventions = len(group[group['Stato'] == 'TERMINATA'])
        completion_rate = (completed_interventions / total_interventions) * 100 if total_interventions > 0 else 0
        
        # Definisce un report "sbrigativo" se ha meno di 20 caratteri
        rushed_reports = len(group[group['Report'].str.len() < 20])

        # Calcola il ritardo medio solo se ci sono dati validi
        avg_delay = group_valid_dates['Ritardo_Compilazione'].mean() if not group_valid_dates.empty else 0

        performance_data[tecnico] = {
            "Totale Interventi": total_interventions,
            "Tasso Completamento (%)": f"{completion_rate:.1f}",
            "Ritardo Medio Compilazione (gg)": f"{avg_delay:.1f}",
            "Report Sbrigativi": rushed_reports
        }
        
    performance_df = pd.DataFrame.from_dict(performance_data, orient='index')
    return performance_df


# --- FUNZIONI INTERFACCIA UTENTE ---
def visualizza_storico_organizzato(storico_list, pdl):
    if storico_list:
        with st.expander(f"Mostra cronologia interventi per PdL {pdl}", expanded=True):
            for intervento in storico_list:
                intervento['data_dt'] = pd.to_datetime(intervento.get('Data_Riferimento'), errors='coerce', dayfirst=True)
            
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
            st.markdown(f"**PdL `{task['pdl']}`** - {task['attivita']}")

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

def render_notification_center(notifications_df, gestionale_data):
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
                    st.caption(notifica['Timestamp'].strftime('%d/%m/%Y %H:%M'))

                with col2:
                    if is_unread:
                        if st.button(" letto", key=f"read_{notifica_id}", help="Segna come letto"):
                            segna_notifica_letta(gestionale_data, notifica_id)
                            salva_gestionale_async(gestionale_data)
                            st.rerun()
                st.divider()

def render_debriefing_ui(knowledge_core, utente, data_riferimento, client_google):
    task = st.session_state.debriefing_task
    section_key = task['section_key']
    is_editing = 'row_index' in task

    # La funzione 'handle_submit' è definita QUI DENTRO
    def handle_submit(report_text, stato, answers_dict=None):
        if report_text.strip():
            # Logica per l'apprendimento
            if answers_dict and 'equipment' in answers_dict and answers_dict['equipment'].startswith("Altro:"):
                report_lines = {k: v for k, v in answers_dict.items() if k != 'equipment'}
                learning_module.add_new_entry(
                    pdl=task['pdl'],
                    attivita=task['attivita'],
                    report_lines=report_lines,
                    tecnico=utente
                )
                st.info("💡 La tua segnalazione per 'Altro' è stata registrata e sarà usata per migliorare il sistema.")

            dati = {
                'descrizione': f"PdL {task['pdl']} - {task['attivita']}",
                'report': report_text,
                'stato': stato,
                'storico': task.get('storico', [])
            }
            row_idx = scrivi_o_aggiorna_risposta(client_google, dati, utente, data_riferimento, row_index=task.get('row_index'))
            if row_idx:
                completed_task_data = {**task, 'report': report_text, 'stato': stato, 'row_index': row_idx, 'answers': answers_dict}
                
                completed_list = st.session_state.get(f"completed_tasks_{section_key}", [])
                completed_list = [t for t in completed_list if t['pdl'] != task['pdl']]
                completed_list.append(completed_task_data)
                st.session_state[f"completed_tasks_{section_key}"] = completed_list

                st.success("Report inviato con successo!")
                del st.session_state.debriefing_task
                if 'answers' in st.session_state:
                    del st.session_state.answers
                st.balloons()
                st.rerun()
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
        tecnici_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Tecnico']['Nome Cognome'].tolist()
        aiutanti_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Aiutante']['Nome Cognome'].tolist()

        tutti_i_contatti = df_contatti['Nome Cognome'].tolist()

        tecnici_selezionati = st.multiselect("Seleziona Tecnici Assegnati", options=tutti_i_contatti, default=tecnici_nel_turno, key="edit_tecnici")
        aiutanti_selezionati = st.multiselect("Seleziona Aiutanti Assegnati", options=tutti_i_contatti, default=aiutanti_nel_turno, key="edit_aiutanti")

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
        personale_originale = set(personale_nel_turno['Nome Cognome'].tolist())
        personale_nuovo = set(tecnici_selezionati + aiutanti_selezionati)
        admin_user = st.session_state.get('authenticated_user', 'N/D')

        personale_rimosso = personale_originale - personale_nuovo
        for utente in personale_rimosso:
            log_shift_change(
                turno_id=turno_id,
                azione="Rimozione Admin",
                utente_originale=utente,
                eseguito_da=admin_user
            )

        personale_aggiunto = personale_nuovo - personale_originale
        for utente in personale_aggiunto:
            log_shift_change(
                turno_id=turno_id,
                azione="Aggiunta Admin",
                utente_subentrante=utente,
                eseguito_da=admin_user
            )

        # 3. Aggiorna le prenotazioni
        # Rimuovi tutte le vecchie prenotazioni per questo turno
        gestionale_data['prenotazioni'] = gestionale_data['prenotazioni'][gestionale_data['prenotazioni']['ID_Turno'] != turno_id]

        # Aggiungi le nuove prenotazioni aggiornate
        nuove_prenotazioni_list = []
        for utente in tecnici_selezionati:
            nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{utente.replace(' ', '')}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()})
        for utente in aiutanti_selezionati:
             nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{utente.replace(' ', '')}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()})

        if nuove_prenotazioni_list:
            df_nuove_prenotazioni = pd.DataFrame(nuove_prenotazioni_list)
            gestionale_data['prenotazioni'] = pd.concat([gestionale_data['prenotazioni'], df_nuove_prenotazioni], ignore_index=True)

        # 4. Invia notifiche per il personale rimosso
        for utente in personale_rimosso:
            messaggio = f"Sei stato rimosso dal turno '{desc_turno}' del {data_turno.strftime('%d/%m/%Y')} dall'amministratore."
            crea_notifica(gestionale_data, utente, messaggio)

        # 5. Salva le modifiche e termina la modalità di modifica
        if salva_gestionale_async(gestionale_data):
            st.success("Turno aggiornato con successo!")
            st.toast("Le modifiche sono state salvate.")
            del st.session_state['editing_turno_id']
            st.rerun()
        else:
            st.error("Si è verificato un errore durante il salvataggio delle modifiche.")

def render_turni_list(df_turni, gestionale, nome_utente_autenticato, ruolo, key_suffix):
    """
    Renderizza una lista di turni, con la logica per la prenotazione, cancellazione e sostituzione.
    """
    if df_turni.empty:
        st.info("Nessun turno di questo tipo disponibile al momento.")
        return

    mostra_solo_disponibili = st.checkbox("Mostra solo turni con posti disponibili", key=f"filter_turni_{key_suffix}")
    st.divider()

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
                for _, p in prenotazioni_turno.iterrows():
                    nome_utente = p['Nome Cognome']
                    ruolo_utente = p['RuoloOccupato']

                    # Check if the user is a placeholder (no password)
                    user_details = df_contatti[df_contatti['Nome Cognome'] == nome_utente] if not df_contatti.empty else pd.DataFrame()

                    # A user is a placeholder if they don't have a password entry.
                    # pd.isna() correctly handles None, NaN, etc.
                    is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('Password'))

                    if is_placeholder:
                        display_name = f"*{nome_utente} (Esterno)*"
                    else:
                        display_name = nome_utente

                    st.markdown(f"- {display_name} (*{ruolo_utente}*)", unsafe_allow_html=True)

            st.markdown("---")

            if ruolo == "Amministratore":
                if st.button("✏️ Modifica Turno", key=f"edit_{turno['ID_Turno']}_{key_suffix}"):
                    st.session_state['editing_turno_id'] = turno['ID_Turno']
                    st.rerun()
                st.markdown("---")

            prenotazione_utente = prenotazioni_turno[prenotazioni_turno['Nome Cognome'] == nome_utente_autenticato]

            if not prenotazione_utente.empty:
                st.success("Sei prenotato per questo turno.")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Cancella Prenotazione", key=f"del_{turno['ID_Turno']}_{key_suffix}", help="Rimuove la tua prenotazione dal turno."):
                        if cancella_prenotazione_logic(gestionale, nome_utente_autenticato, turno['ID_Turno']):
                            salva_gestionale_async(gestionale); st.rerun()
                with col2:
                    if st.button("📢 Pubblica in Bacheca", key=f"pub_{turno['ID_Turno']}_{key_suffix}", help="Rilascia il tuo turno e rendilo disponibile a tutti in bacheca."):
                        if pubblica_turno_in_bacheca_logic(gestionale, nome_utente_autenticato, turno['ID_Turno']):
                            salva_gestionale_async(gestionale); st.rerun()
                with col3:
                    if st.button("🔄 Chiedi Sostituzione", key=f"ask_{turno['ID_Turno']}_{key_suffix}", help="Chiedi a un collega specifico di sostituirti."):
                        st.session_state['sostituzione_turno_id'] = turno['ID_Turno']; st.rerun()
            else:
                opzioni = []
                if tecnici_prenotati < posti_tecnico: opzioni.append("Tecnico")
                if aiutanti_prenotati < posti_aiutante: opzioni.append("Aiutante")
                if opzioni:
                    ruolo_scelto = st.selectbox("Prenota come:", opzioni, key=f"sel_{turno['ID_Turno']}_{key_suffix}")
                    if st.button("Conferma Prenotazione", key=f"add_{turno['ID_Turno']}_{key_suffix}"):
                        if prenota_turno_logic(gestionale, nome_utente_autenticato, turno['ID_Turno'], ruolo_scelto):
                            salva_gestionale_async(gestionale); st.rerun()
                else:
                    st.warning("Turno al completo.")
                    if st.button("Chiedi Sostituzione", key=f"ask_full_{turno['ID_Turno']}_{key_suffix}"):
                        st.session_state['sostituzione_turno_id'] = turno['ID_Turno']; st.rerun()

            if st.session_state.get('sostituzione_turno_id') == turno['ID_Turno']:
                st.markdown("---")
                st.markdown("**A chi vuoi chiedere il cambio?**")
                ricevente_options = prenotazioni_turno['Nome Cognome'].tolist() if not prenotazione_utente.empty else gestionale['contatti']['Nome Cognome'].tolist()
                ricevente = st.selectbox("Seleziona collega:", ricevente_options, key=f"swap_select_{turno['ID_Turno']}_{key_suffix}")
                if st.button("Invia Richiesta", key=f"swap_confirm_{turno['ID_Turno']}_{key_suffix}"):
                    if richiedi_sostituzione_logic(gestionale, nome_utente_autenticato, ricevente, turno['ID_Turno']):
                        salva_gestionale_async(gestionale); del st.session_state['sostituzione_turno_id']; st.rerun()

def render_gestione_account(gestionale_data):
    df_contatti = gestionale_data['contatti']

    # --- Modifica Utenti Esistenti ---
    st.subheader("Modifica Utenti Esistenti")

    if 'editing_user' not in st.session_state:
        st.session_state.editing_user = None

    # Se un utente è in modifica, mostra solo il form di modifica
    if st.session_state.editing_user:
        user_to_edit_series = df_contatti[df_contatti['Nome Cognome'] == st.session_state.editing_user]
        if not user_to_edit_series.empty:
            user_to_edit = user_to_edit_series.iloc[0]
            with st.form(key="edit_user_form"):
                st.subheader(f"Modifica Utente: {st.session_state.editing_user}")

                ruoli_disponibili = ["Tecnico", "Aiutante", "Amministratore"]
                try:
                    current_role_index = ruoli_disponibili.index(user_to_edit['Ruolo'])
                except ValueError:
                    current_role_index = 0 # Default a Tecnico se il ruolo non è standard

                new_role = st.selectbox("Nuovo Ruolo", options=ruoli_disponibili, index=current_role_index)

                is_placeholder_current = pd.isna(user_to_edit.get('PasswordHash')) and pd.isna(user_to_edit.get('Password'))
                is_placeholder_new = st.checkbox("Imposta come Utente Placeholder (senza accesso)", value=is_placeholder_current)

                new_password = ""
                if not is_placeholder_new:
                    new_password = st.text_input("Nuova Password (lasciare vuoto per non modificare)", type="password")

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Salva Modifiche", type="primary"):
                        user_idx = df_contatti[df_contatti['Nome Cognome'] == st.session_state.editing_user].index[0]
                        df_contatti.loc[user_idx, 'Ruolo'] = new_role

                        if is_placeholder_new:
                            df_contatti.loc[user_idx, 'PasswordHash'] = None
                            if 'Password' in df_contatti.columns:
                                df_contatti.loc[user_idx, 'Password'] = None
                            st.success(f"L'utente {st.session_state.editing_user} è stato impostato come Placeholder.")
                        elif new_password:
                            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                            df_contatti.loc[user_idx, 'PasswordHash'] = hashed.decode('utf-8')
                            if 'Password' in df_contatti.columns:
                                df_contatti.loc[user_idx, 'Password'] = None
                            st.success(f"Password per {st.session_state.editing_user} aggiornata.")

                        salva_gestionale_async(gestionale_data)
                        st.session_state.editing_user = None
                        st.toast("Modifiche salvate!")
                        st.rerun()

                with col2:
                    if st.form_submit_button("Annulla"):
                        st.session_state.editing_user = None
                        st.rerun()
        else:
            st.error("Utente non trovato. Ricaricamento...")
            st.session_state.editing_user = None
            st.rerun()

    # Altrimenti, mostra la lista di tutti gli utenti
    else:
        for index, user in df_contatti.iterrows():
            user_name = user['Nome Cognome']
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{user_name}**")
                with col2:
                    is_placeholder = pd.isna(user.get('PasswordHash')) and pd.isna(user.get('Password'))
                    status = "Placeholder (senza accesso)" if is_placeholder else "Attivo"
                    st.markdown(f"*{user['Ruolo']}* - Stato: *{status}*")
                with col3:
                    if st.button("Modifica", key=f"edit_{user_name}"):
                        st.session_state.editing_user = user_name
                        st.rerun()

                # Aggiungi colonna per reset 2FA
                has_2fa = '2FA_Secret' in user and pd.notna(user['2FA_Secret']) and user['2FA_Secret']
                if has_2fa:
                    with col1:
                        if st.button("Resetta 2FA", key=f"reset_2fa_{user_name}", help="Rimuove la 2FA per questo utente. Dovrà configurarla di nuovo al prossimo accesso."):
                            user_idx = df_contatti[df_contatti['Nome Cognome'] == user_name].index[0]
                            df_contatti.loc[user_idx, '2FA_Secret'] = None
                            salva_gestionale_async(gestionale_data)
                            st.success(f"2FA resettata per {user_name}.")
                            st.rerun()

    st.divider()

    # --- Crea Nuovo Utente Placeholder ---
    with st.expander("Crea Nuovo Utente Placeholder"):
        with st.form("new_user_form", clear_on_submit=True):
            st.subheader("Dati Nuovo Utente")
            c1, c2 = st.columns(2)
            new_nome = c1.text_input("Nome")
            new_cognome = c2.text_input("Cognome")
            new_ruolo = st.selectbox("Ruolo", ["Tecnico", "Aiutante", "Amministratore"])

            submitted_new_user = st.form_submit_button("Crea Utente")

            if submitted_new_user:
                if new_nome and new_cognome:
                    nome_completo = f"{new_nome.strip()} {new_cognome.strip()}"
                    if nome_completo in df_contatti['Nome Cognome'].tolist():
                        st.error(f"Errore: L'utente '{nome_completo}' esiste già.")
                    else:
                        new_user_data = {
                            'Nome Cognome': nome_completo,
                            'Ruolo': new_ruolo,
                            'Password': None,
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
                            st.success(f"Utente placeholder '{nome_completo}' creato con successo!")
                            st.rerun()
                        else:
                            st.error("Errore durante il salvataggio del nuovo utente.")
                else:
                    st.warning("Nome e Cognome sono obbligatori.")


def render_technician_detail_view():
    """Mostra la vista di dettaglio per un singolo tecnico."""
    tecnico = st.session_state['detail_technician']
    start_date = st.session_state['detail_start_date']
    end_date = st.session_state['detail_end_date']

    st.title(f"Dettaglio Performance: {tecnico}")
    st.markdown(f"Periodo: **{start_date.strftime('%d/%m/%Y')}** - **{end_date.strftime('%d/%m/%Y')}**")

    # Recupera le metriche già calcolate dalla sessione
    if 'performance_results' in st.session_state:
        performance_df = st.session_state['performance_results']['df']
        if tecnico in performance_df.index:
            technician_metrics = performance_df.loc[tecnico]
            
            # Mostra le metriche specifiche per il tecnico
            st.markdown("#### Riepilogo Metriche")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Totale Interventi", technician_metrics['Totale Interventi'])
        c2.metric("Tasso Completamento", f"{technician_metrics['Tasso Completamento (%)']}%")
        c3.metric("Ritardo Medio (gg)", technician_metrics['Ritardo Medio Compilazione (gg)'])
        c4.metric("Report Sbrigativi", technician_metrics['Report Sbrigativi'])
        st.markdown("---")

    if st.button("⬅️ Torna alla Dashboard"):
        del st.session_state['detail_technician']
        del st.session_state['detail_start_date']
        del st.session_state['detail_end_date']
        st.rerun()

    archivio_df = carica_archivio_completo()
    mask = (
        (archivio_df['Tecnico'] == tecnico) &
        (archivio_df['Data_Riferimento_dt'] >= start_date) &
        (archivio_df['Data_Riferimento_dt'] <= end_date)
    )
    technician_interventions = archivio_df[mask]

    if technician_interventions.empty:
        st.warning("Nessun intervento trovato per questo tecnico nel periodo selezionato.")
        return

    st.markdown("### Riepilogo Interventi")
    # Formatta la colonna della data prima di visualizzarla
    technician_interventions['Data'] = technician_interventions['Data_Riferimento_dt'].dt.strftime('%d/%m/%Y')
    st.dataframe(technician_interventions[['Data', 'PdL', 'Descrizione', 'Stato', 'Report']])

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
        interventions_by_day = technician_interventions.groupby(technician_interventions['Data_Riferimento_dt'].dt.date).size()
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

def render_reperibilita_tab(gestionale_data, nome_utente_autenticato, ruolo_utente):
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
        user_to_manage = st.session_state.managing_oncall_user

        with st.container(border=True):
            st.subheader("Gestione Turno di Reperibilità")
            try:
                turno_info = gestionale_data['turni'][gestionale_data['turni']['ID_Turno'] == shift_id_to_manage].iloc[0]
                st.write(f"Stai modificando il turno di **{user_to_manage}** per il giorno **{pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')}**.")
            except IndexError:
                st.error("Dettagli del turno non trovati.")
                # Aggiungiamo un pulsante per uscire in caso di errore
                if st.button("⬅️ Torna al Calendario"):
                     if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                     st.rerun()
                st.stop()


            if st.session_state.get('oncall_swap_mode'):
                st.markdown("**A chi vuoi chiedere il cambio?**")
                contatti_validi = gestionale_data['contatti'][
                    (gestionale_data['contatti']['Nome Cognome'] != user_to_manage) &
                    (gestionale_data['contatti']['PasswordHash'].notna())
                ]
                ricevente = st.selectbox("Seleziona collega:", contatti_validi['Nome Cognome'].tolist(), key=f"swap_select_{shift_id_to_manage}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Invia Richiesta", key=f"swap_confirm_{shift_id_to_manage}", use_container_width=True, type="primary"):
                        if richiedi_sostituzione_logic(gestionale_data, user_to_manage, ricevente, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                            st.rerun()
                with c2:
                    if st.button("Annulla Scambio", use_container_width=True):
                        del st.session_state.oncall_swap_mode
                        st.rerun()
            else:
                st.info("Cosa vuoi fare con questo turno?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📢 Pubblica in Bacheca", use_container_width=True):
                        if pubblica_turno_in_bacheca_logic(gestionale_data, user_to_manage, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            st.rerun()
                with col2:
                    if st.button("🔄 Chiedi Sostituzione", use_container_width=True):
                        st.session_state.oncall_swap_mode = True
                        st.rerun()

            st.divider()
            if st.button("⬅️ Torna al Calendario", key=f"cancel_manage_{shift_id_to_manage}", use_container_width=True):
                if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                if 'managing_oncall_user' in st.session_state: del st.session_state.managing_oncall_user
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
        if st.button("⬅️", help="Settimana precedente", use_container_width=True):
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
        if st.button("➡️", help="Settimana successiva", use_container_width=True):
            st.session_state.week_start_date += datetime.timedelta(weeks=1)
            st.rerun()

    if st.button("Vai a Oggi", use_container_width=True):
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
            managed_user_name = nome_utente_autenticato

            if not shift_today.empty:
                shift_id_today = shift_today.iloc[0]['ID_Turno']
                prenotazioni_today = df_prenotazioni[df_prenotazioni['ID_Turno'] == shift_id_today]
                df_contatti = gestionale_data.get('contatti', pd.DataFrame())


                if not prenotazioni_today.empty:
                    tech_display_list = []
                    for _, booking in prenotazioni_today.iterrows():
                        technician_name = booking['Nome Cognome']
                        surname = technician_name.split()[-1].upper()

                        # --- LOGICA PLACEHOLDER ---
                        user_details = df_contatti[df_contatti['Nome Cognome'] == technician_name] if not df_contatti.empty else pd.DataFrame()
                        is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('Password')) or pd.isna(user_details.iloc[0].get('PasswordHash'))

                        if is_placeholder:
                            display_name = f"<i>{surname} (Esterno)</i>"
                        else:
                            display_name = surname
                        tech_display_list.append(display_name)
                        # --- FINE LOGICA PLACEHOLDER ---

                        if technician_name == nome_utente_autenticato:
                            user_is_on_call = True

                    if tech_display_list:
                        managed_user_name = prenotazioni_today.iloc[0]['Nome Cognome']

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
                if st.button("Gestisci", key=f"manage_{day}", use_container_width=True):
                    st.session_state.managing_oncall_shift_id = shift_id_today
                    st.session_state.managing_oncall_user = managed_user_name
                    st.rerun()


def render_guida_tab(ruolo):
    st.title("❓ Guida")
    st.write("Benvenuto nella guida utente! Qui troverai le istruzioni per usare al meglio l'applicazione.")
    st.info("Usa i menù a tendina qui sotto per esplorare le diverse sezioni e funzionalità dell'app. La tua sessione ora rimane attiva anche se aggiorni la pagina!")

    # Sezione Attività
    with st.expander("📝 Le Tue Attività (Oggi e Giorno Precedente)", expanded=True):
        st.subheader("Compilare un Report")
        st.markdown("""
        In questa sezione vedi le attività che ti sono state assegnate per la giornata.
        - Per ogni attività, vedrai il codice **PdL** e una breve descrizione.
        - Se lavori in **Team**, vedrai i nomi dei tuoi colleghi, il loro ruolo e gli orari di lavoro per quell'attività.
        - Puoi scegliere tra due modalità di compilazione:
            - **✍️ Compila Report Guidato (IA)**: Una procedura a domande che ti aiuta a scrivere un report completo e standardizzato.
            - **📝 Compila Report Manuale**: Un campo di testo libero dove puoi scrivere il report come preferisci.
        - **Importante per gli Aiutanti**: Se fai parte di un team con più persone, solo un **Tecnico** può compilare il report. Potrai vedere l'attività e il report una volta compilato, ma non potrai inviarlo. Se lavori da solo, puoi compilare il report normalmente.
        """)
        st.subheader("Vedere lo Storico")
        st.markdown("Sotto ogni attività, puoi espandere la sezione 'Mostra cronologia interventi' per vedere tutti i report passati relativi a quel PdL. Questo è utile per capire i problemi ricorrenti.")

    with st.expander("📊 Situazione Impianti"):
        st.subheader("Avere una Visione d'Insieme")
        st.markdown("""
        Questa sezione ti offre una panoramica dello stato di tutte le attività pianificate nel file Excel, arricchite con lo stato di avanzamento reale preso dall'applicazione.
        - **Come funziona?** Il sistema unisce i dati, dando sempre la priorità allo stato più aggiornato (quello dei report compilati).
        - **Filtri**: Puoi filtrare la vista per **TCL**, **Area** e **Stato**.
        - **Importante**: Dopo aver selezionato i filtri, clicca sul pulsante **"Applica Filtri"** per aggiornare i grafici e la tabella con i risultati.
        """)

    with st.expander("🗓️ Programmazione Attività"):
        st.subheader("Vedere le Attività Programmate")
        st.markdown("""
        Qui puoi vedere quali attività sono state programmate per la settimana e consultarne tutti i dettagli in un unico posto.
        - Ogni attività è presentata in una "card" separata per una facile consultazione.
        - **Dettagli nella Card**:
            - Dati principali (PdL, Impianto, TCL, Area).
            - Lo **stato attuale** dell'attività.
            - La **descrizione completa** dell'attività.
            - I **giorni della settimana** in cui è programmata.
        - **Storico Interventi**: Se per un PdL sono già stati eseguiti interventi, puoi cliccare su `"Mostra cronologia interventi"` direttamente dentro la card per vedere lo storico, senza doverlo cercare nell'archivio.
        - **Filtri**: Puoi cercare attività specifiche usando i filtri per **PdL**, **Area**, **TCL** o **Giorno** della settimana. Anche qui, ricorda di cliccare su **"Applica Filtri"** per avviare la ricerca.
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
        with st.expander("🔑 Gestione Account (Solo Admin)"):
            st.subheader("Modificare un Utente")
            st.markdown("""
            Nella `Dashboard Admin > Gestione Account`, vedrai l'elenco di tutti gli utenti.
            - Clicca su **"Modifica"** per cambiare i dati di un utente.
            - **Cambiare Ruolo**: Puoi promuovere un utente a "Amministratore" o cambiarne il ruolo.
            - **Reset Password**: Inserisci una nuova password nel campo apposito per aggiornarla.
            - **Utente Placeholder**: Spunta la casella "Imposta come Utente Placeholder" per trasformare un account in un utente "esterno". Questo utente non potrà accedere all'applicazione, ma il suo nome potrà essere ancora assegnato ai turni. Per riattivare l'utente, togli la spunta e assegnagli una nuova password.
            """)
            st.subheader("Creare un Utente Placeholder")
            st.markdown("Usa il modulo in fondo alla pagina per creare rapidamente un nuovo utente esterno che non necessita di accesso, ma che deve comparire nel sistema.")

    # Sezione Archivio
    with st.expander("🗂️ Ricerca nell'Archivio"):
        st.subheader("Trovare Vecchi Report")
        st.markdown("Usa questa sezione per cercare tra tutti i report compilati in passato. Puoi filtrare per:")
        st.markdown("""
        - **PdL**: Per vedere tutti gli interventi su un punto specifico.
        - **Descrizione**: Per cercare parole chiave nell'attività.
        - **Tecnico**: Per vedere tutti i report compilati da uno o più colleghi.
        """)


# --- GESTIONE SESSIONE ---
SESSION_FILE = f"session_{os.getlogin()}.json"
SESSION_DURATION_HOURS = 8

def save_session(username, role):
    """Salva la sessione utente su un file."""
    session_data = {
        'authenticated_user': username,
        'ruolo': role,
        'timestamp': datetime.datetime.now().isoformat()
    }
    try:
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f)
    except IOError as e:
        st.error(f"Impossibile salvare la sessione: {e}")

def load_session():
    """Carica la sessione utente da un file se valida e non scaduta."""
    if st.session_state.get('authenticated_user'):
        return

    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                session_data = json.load(f)

            session_time = datetime.datetime.fromisoformat(session_data['timestamp'])
            if datetime.datetime.now() - datetime.timedelta(hours=SESSION_DURATION_HOURS) < session_time:
                st.session_state.authenticated_user = session_data['authenticated_user']
                st.session_state.ruolo = session_data['ruolo']
            else:
                # Sessione scaduta, pulisci
                delete_session()
        except (IOError, json.JSONDecodeError, KeyError):
            # File corrotto, pulisci
            delete_session()

def delete_session():
    """Cancella il file di sessione e pulisce lo stato di streamlit."""
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except OSError:
            pass  # Ignora errori in cancellazione se il file è bloccato

    # Pulisce completamente lo stato della sessione per un logout sicuro
    keys_to_clear = [k for k in st.session_state.keys()]
    for key in keys_to_clear:
        del st.session_state[key]


# --- APPLICAZIONE STREAMLIT PRINCIPALE ---
def render_situazione_impianti_tab():
    st.header("📊 Situazione Generale Impianti")

    # Carica i dati aggiornati
    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Non sono stati trovati dati sulle attività programmate. Verificare il file Excel.")
        st.info("Questa sezione mostra lo stato di avanzamento delle attività (es. SOSPESO, COMPLETATO) raggruppate per Area e TCL.")
        return

    with st.form("situazione_filters_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_tcl = st.multiselect(
                "Filtra per TCL",
                options=sorted(df['TCL'].unique()),
                default=sorted(df['TCL'].unique())
            )
        with col2:
            selected_area = st.multiselect(
                "Filtra per Area",
                options=sorted(df['Area'].unique()),
                default=sorted(df['Area'].unique())
            )
        with col3:
            selected_stato = st.multiselect(
                "Filtra per Stato",
                options=sorted(df['Stato'].unique()),
                default=sorted(df['Stato'].unique())
            )

        submitted = st.form_submit_button("Applica Filtri")

    if not submitted:
        st.info("Usa i filtri e clicca su 'Applica Filtri' per visualizzare i dati.")
        return

    if not selected_tcl or not selected_area or not selected_stato:
        st.warning("Seleziona almeno un valore per ogni filtro.")
        return

    # Applica i filtri
    filtered_df = df[
        df['TCL'].isin(selected_tcl) &
        df['Area'].isin(selected_area) &
        df['Stato'].isin(selected_stato)
    ].copy()

    if filtered_df.empty:
        st.info("Nessuna attività corrisponde ai filtri selezionati.")
        return

    # --- Visualizzazione Dati ---
    st.subheader("Riepilogo Attività per Stato")

    # Calcola le metriche
    total_activities = len(filtered_df)
    status_counts = filtered_df['Stato'].value_counts()

    # Se la colonna STATO non è ancora stata definita, mostra un avviso
    if "Non Definito" in status_counts.index:
        st.info("NOTA: La colonna 'Stato' non è stata ancora configurata. I dati seguenti sono aggregati su un valore di default.")

    st.metric("Totale Attività Filtrate", total_activities)

    st.markdown("##### Conteggio per Stato")
    st.dataframe(status_counts)

    # Grafico a barre
    if not (status_counts.index == "Non Definito").all():
        st.bar_chart(status_counts)

    st.subheader("Dettaglio Attività Filtrate")
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"#### PdL `{row['PdL']}`")
                st.markdown(f"**Impianto:** {row.get('Impianto', 'N/D')} | **Area:** {row.get('Area', 'N/D')} | **TCL:** {row.get('TCL', 'N/D')}")
            with col2:
                st.markdown(f"**Stato Attuale**")
                st.info(f"_{row['Stato']}_")

            if pd.notna(row['Descrizione']):
                st.caption(f"Descrizione: {row['Descrizione']}")

            st.markdown(f"**Programmato per:** 🗓️ `{row['GiorniProgrammati']}`")

            if row['Storico']:
                visualizza_storico_organizzato(row['Storico'], row['PdL'])


def render_programmazione_tab():
    st.header("🗓️ Programmazione Attività Settimanale")

    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Non sono stati trovati dati sulle attività programmate.")
        return

    # Filtra per mostrare solo le attività effettivamente programmate
    scheduled_df = df[df['GiorniProgrammati'] != 'Non Programmato'].copy()

    if scheduled_df.empty:
        st.info("Nessuna attività risulta programmata per la settimana corrente nel file Excel.")
        return

    st.info(f"Sono state trovate {len(scheduled_df)} attività programmate.")

    with st.form("programmazione_filters_form"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            pdl_filter = st.text_input("Filtra per PdL...")
        with col2:
            area_filter = st.multiselect("Filtra per Area", options=sorted(scheduled_df['Area'].unique()))
        with col3:
            tcl_filter = st.multiselect("Filtra per TCL", options=sorted(scheduled_df['TCL'].unique()))
        with col4:
            day_filter = st.multiselect("Filtra per Giorno", options=["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"])

        submitted = st.form_submit_button("Applica Filtri")

    if not submitted:
        st.info("Usa i filtri e clicca su 'Applica Filtri' per visualizzare i dati.")
        return

    # Applica filtri
    if pdl_filter:
        scheduled_df = scheduled_df[scheduled_df['PdL'].astype(str).str.contains(pdl_filter, case=False, na=False)]
    if area_filter:
        scheduled_df = scheduled_df[scheduled_df['Area'].isin(area_filter)]
    if tcl_filter:
        scheduled_df = scheduled_df[scheduled_df['TCL'].isin(tcl_filter)]
    if day_filter:
        day_regex = '|'.join(day_filter)
        scheduled_df = scheduled_df[scheduled_df['GiorniProgrammati'].str.contains(day_regex, case=False, na=False)]

    st.divider()

    if scheduled_df.empty:
        st.info("Nessuna attività programmata corrisponde ai filtri selezionati.")
        return

    # Layout a card, mobile-friendly (reso coerente con la tab Situazione Impianti)
    for index, row in scheduled_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"#### PdL `{row['PdL']}`")
                st.markdown(f"**Impianto:** {row.get('Impianto', 'N/D')} | **Area:** {row.get('Area', 'N/D')} | **TCL:** {row.get('TCL', 'N/D')}")
            with col2:
                st.markdown(f"**Stato Attuale**")
                st.info(f"_{row['Stato']}_")

            if pd.notna(row['Descrizione']):
                st.caption(f"Descrizione: {row['Descrizione']}")

            st.markdown(f"**Programmato per:** 🗓️ `{row['GiorniProgrammati']}`")

            # Mostra storico interventi
            if row['Storico']:
                visualizza_storico_organizzato(row['Storico'], row['PdL'])


def main_app(nome_utente_autenticato, ruolo):
    st.set_page_config(layout="wide", page_title="Report Attività")

    gestionale_data = carica_gestionale()

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
            render_debriefing_ui(knowledge_core, nome_utente_autenticato, datetime.date.today(), autorizza_google())
    else:
        # Header con titolo, notifiche e pulsante di logout
        col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
        with col1:
            st.title(f"Report Attività")
            st.header(f"Ciao, {nome_utente_autenticato}!")
            st.caption(f"Ruolo: {ruolo}")
        with col2:
            st.write("") # Spacer
            st.write("") # Spacer
            user_notifications = leggi_notifiche(gestionale_data, nome_utente_autenticato)
            render_notification_center(user_notifications, gestionale_data)
        with col3:
            st.write("")
            st.write("")
            if st.button("Logout", type="secondary"):
                delete_session()
                st.rerun()

        oggi = datetime.date.today()
        giorno_precedente = oggi - datetime.timedelta(days=1)
        if oggi.weekday() == 0: giorno_precedente = oggi - datetime.timedelta(days=3)
        elif oggi.weekday() == 6: giorno_precedente = oggi - datetime.timedelta(days=2)
        
        if ruolo in ["Amministratore", "Tecnico"]:
            attivita_pianificate_ieri = trova_attivita(nome_utente_autenticato, giorno_precedente.day, giorno_precedente.month, giorno_precedente.year, gestionale_data['contatti'])
            num_attivita_mancanti = 0
            if attivita_pianificate_ieri:
                archivio_df = carica_archivio_completo()
                pdl_compilati_ieri = set(archivio_df[(archivio_df['Tecnico'] == nome_utente_autenticato) & (archivio_df['Data_Riferimento_dt'].dt.date == giorno_precedente)]['PdL']) if not archivio_df.empty else set()
                num_attivita_mancanti = len(attivita_pianificate_ieri) - len(pdl_compilati_ieri)
            if num_attivita_mancanti > 0:
                st.warning(f"**Promemoria:** Hai **{num_attivita_mancanti} attività** del giorno precedente non compilate.")

        lista_tab = ["Attività di Oggi", "Attività Giorno Precedente", "📊 Situazione Impianti", "🗓️ Programmazione Attività", "Ricerca nell'Archivio", "📅 Gestione Turni", "❓ Guida"]
        if ruolo == "Amministratore":
            lista_tab.append("Dashboard Admin")
        
        tabs = st.tabs(lista_tab)
        
        with tabs[0]:
            st.header(f"Attività del {oggi.strftime('%d/%m/%Y')}")
            lista_attivita = trova_attivita(nome_utente_autenticato, oggi.day, oggi.month, oggi.year, gestionale_data['contatti'])
            disegna_sezione_attivita(lista_attivita, "today", ruolo)

        with tabs[1]:
            st.header(f"Recupero attività del {giorno_precedente.strftime('%d/%m/%Y')}")
            lista_attivita_ieri_totale = trova_attivita(nome_utente_autenticato, giorno_precedente.day, giorno_precedente.month, giorno_precedente.year, gestionale_data['contatti'])
            archivio_df = carica_archivio_completo()
            pdl_compilati_ieri = set()
            if not archivio_df.empty:
                report_compilati = archivio_df[(archivio_df['Tecnico'] == nome_utente_autenticato) & (archivio_df['Data_Riferimento_dt'].dt.date == giorno_precedente)]
                pdl_compilati_ieri = set(report_compilati['PdL'])

            attivita_da_recuperare = [task for task in lista_attivita_ieri_totale if task['pdl'] not in pdl_compilati_ieri]
            disegna_sezione_attivita(attivita_da_recuperare, "yesterday", ruolo)

        with tabs[2]:
            render_situazione_impianti_tab()

        with tabs[3]:
            render_programmazione_tab()

        with tabs[4]:
            st.header("🗂️ Archivio e Ricerca Avanzata")
            st.info("Cerca in tutte le attività usando filtri avanzati.")

            df = get_processed_activities()
            if df.empty:
                st.warning("Dati attività non disponibili.")
                return

            with st.expander("Applica Filtri di Ricerca", expanded=True):
                with st.form("archive_filters"):
                    c1, c2 = st.columns(2)
                    with c1:
                        keyword_filter = st.text_input("Parola chiave in Descrizione o Report...")
                        personale_filter = st.text_input("Filtra per Personale...")
                    with c2:
                        # Trova dinamicamente la colonna data
                        col_data = find_column_by_keywords(df, ['data', 'controllo'])
                        min_date = df[col_data].min().date() if col_data and not df[col_data].dropna().empty else datetime.date.today()
                        max_date = df[col_data].max().date() if col_data and not df[col_data].dropna().empty else datetime.date.today()

                        date_range = st.date_input(
                            "Filtra per Intervallo Date",
                            value=(min_date, max_date),
                            min_value=min_date,
                            max_value=max_date,
                            format="DD/MM/YYYY"
                        )

                    submitted = st.form_submit_button("Cerca nell'Archivio")

            if submitted:
                filtered_df = df.copy()

                # Applica filtro keyword
                if keyword_filter:
                    col_desc = find_column_by_keywords(filtered_df, ['descrizione', 'attivita'])
                    col_report = find_column_by_keywords(filtered_df, ['stato', 'attivita'])

                    desc_match = pd.Series([False] * len(filtered_df))
                    report_match = pd.Series([False] * len(filtered_df))

                    if col_desc:
                        desc_match = filtered_df[col_desc].astype(str).str.contains(keyword_filter, case=False, na=False)
                    if col_report:
                        report_match = filtered_df[col_report].astype(str).str.contains(keyword_filter, case=False, na=False)

                    filtered_df = filtered_df[desc_match | report_match]

                # Applica filtro personale
                if personale_filter:
                    col_personale = find_column_by_keywords(filtered_df, ['personale', 'impiegato'])
                    if col_personale:
                        filtered_df = filtered_df[filtered_df[col_personale].astype(str).str.contains(personale_filter, case=False, na=False)]

                # Applica filtro data
                if len(date_range) == 2 and col_data:
                    start_date = pd.to_datetime(date_range[0])
                    end_date = pd.to_datetime(date_range[1])
                    filtered_df = filtered_df[(filtered_df[col_data] >= start_date) & (filtered_df[col_data] <= end_date)]

                st.divider()

                if filtered_df.empty:
                    st.warning("Nessuna attività trovata con i criteri di ricerca specificati.")
                else:
                    st.success(f"Trovate {len(filtered_df)} voci di attività corrispondenti.")
                    grouped_by_pdl = filtered_df.groupby('PdL')
                    for pdl, group in grouped_by_pdl:
                        display_expandable_activity_card(pdl, group, "arch", container=st)
            else:
                st.info("Imposta i filtri e clicca su 'Cerca nell'Archivio' per avviare la ricerca.")

        with tabs[5]:
            st.subheader("Gestione Turni")
            turni_disponibili_tab, bacheca_tab, sostituzioni_tab, reperibilita_tab = st.tabs(["📅 Turni", "📢 Bacheca", "🔄 Sostituzioni", "🗓️ Turni Reperibilità"])

            with turni_disponibili_tab:
                assistenza_tab, straordinario_tab = st.tabs(["Turni Assistenza", "Turni Straordinario"])
                df_turni_totale = gestionale_data['turni'].copy()
                df_turni_totale.dropna(subset=['ID_Turno'], inplace=True)

                with assistenza_tab:
                    df_assistenza = df_turni_totale[df_turni_totale['Tipo'] == 'Assistenza']
                    render_turni_list(df_assistenza, gestionale_data, nome_utente_autenticato, ruolo, "assistenza")

                with straordinario_tab:
                    df_straordinario = df_turni_totale[df_turni_totale['Tipo'] == 'Straordinario']
                    render_turni_list(df_straordinario, gestionale_data, nome_utente_autenticato, ruolo, "straordinario")

            with bacheca_tab:
                st.subheader("Turni Liberi in Bacheca")
                df_bacheca = gestionale_data.get('bacheca', pd.DataFrame())
                turni_disponibili_bacheca = df_bacheca[df_bacheca['Stato'] == 'Disponibile'].sort_values(by='Timestamp_Pubblicazione', ascending=False)

                if turni_disponibili_bacheca.empty:
                    st.info("Al momento non ci sono turni liberi in bacheca.")
                else:
                    df_turni = gestionale_data['turni']
                    for _, bacheca_entry in turni_disponibili_bacheca.iterrows():
                        try:
                            turno_details = df_turni[df_turni['ID_Turno'] == bacheca_entry['ID_Turno']].iloc[0]
                            with st.container(border=True):
                                st.markdown(f"**{turno_details['Descrizione']}** ({bacheca_entry['Ruolo_Originale']})")
                                st.caption(f"Data: {pd.to_datetime(turno_details['Data']).strftime('%d/%m/%Y')} | Orario: {turno_details['OrarioInizio']} - {turno_details['OrarioFine']}")
                                st.write(f"Pubblicato da: {bacheca_entry['Tecnico_Originale']} il {pd.to_datetime(bacheca_entry['Timestamp_Pubblicazione']).strftime('%d/%m %H:%M')}")

                                ruolo_richiesto = bacheca_entry['Ruolo_Originale']
                                is_eligible = not (ruolo_richiesto == 'Tecnico' and ruolo == 'Aiutante')

                                if is_eligible:
                                    if st.button("Prendi questo turno", key=f"take_{bacheca_entry['ID_Bacheca']}"):
                                        if prendi_turno_da_bacheca_logic(gestionale_data, nome_utente_autenticato, ruolo, bacheca_entry['ID_Bacheca']):
                                            salva_gestionale_async(gestionale_data)
                                            st.rerun()
                                else:
                                    st.info("Non hai il ruolo richiesto per questo turno.")
                        except IndexError:
                            st.warning(f"Dettagli non trovati per il turno ID {bacheca_entry['ID_Turno']}. Potrebbe essere stato rimosso.")


            with sostituzioni_tab:
                st.subheader("Richieste di Sostituzione")
                df_sostituzioni = gestionale_data['sostituzioni']
                st.markdown("#### 📥 Richieste Ricevute")
                richieste_ricevute = df_sostituzioni[df_sostituzioni['Ricevente'] == nome_utente_autenticato]
                if richieste_ricevute.empty: st.info("Nessuna richiesta di sostituzione ricevuta.")
                for _, richiesta in richieste_ricevute.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{richiesta['Richiedente']}** ti ha chiesto un cambio per il turno **{richiesta['ID_Turno']}**.")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Accetta", key=f"acc_{richiesta['ID_Richiesta']}"):
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], nome_utente_autenticato, True):
                                    salva_gestionale_async(gestionale_data); st.rerun()
                        with c2:
                            if st.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                                if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], nome_utente_autenticato, False):
                                    salva_gestionale_async(gestionale_data); st.rerun()
                st.divider()
                st.markdown("#### 📤 Richieste Inviate")
                richieste_inviate = df_sostituzioni[df_sostituzioni['Richiedente'] == nome_utente_autenticato]
                if richieste_inviate.empty: st.info("Nessuna richiesta di sostituzione inviata.")
                for _, richiesta in richieste_inviate.iterrows():
                    st.markdown(f"- Richiesta inviata a **{richiesta['Ricevente']}** per il turno **{richiesta['ID_Turno']}**.")

            with reperibilita_tab:
                render_reperibilita_tab(gestionale_data, nome_utente_autenticato, ruolo)

        with tabs[6]:
            render_guida_tab(ruolo)

        if len(tabs) > 7 and ruolo == "Amministratore":
            with tabs[7]:
                st.subheader("Dashboard di Controllo")

                # Se è stata selezionata la vista di dettaglio, mostrala
                if st.session_state.get('detail_technician'):
                    render_technician_detail_view()
                else:
                    # Altrimenti, mostra le tab principali della dashboard
                    admin_tabs = st.tabs(["Performance Team", "Revisione Conoscenze", "Crea Nuovo Turno", "Gestione Account"])

                    with admin_tabs[0]: # Performance Team
                        archivio_df_perf = carica_archivio_completo()
                        if archivio_df_perf.empty:
                            st.warning("Archivio storico non disponibile o vuoto. Impossibile calcolare le performance.")
                        else:
                            st.markdown("#### Seleziona Intervallo Temporale")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                start_date = st.date_input(
                                    "Data di Inizio", 
                                    datetime.date.today() - datetime.timedelta(days=30),
                                    format="DD/MM/YYYY",
                                    key="perf_start_date"
                                )
                            with col2:
                                end_date = st.date_input(
                                    "Data di Fine", 
                                    datetime.date.today(),
                                    format="DD/MM/YYYY",
                                    key="perf_end_date"
                                )

                            start_datetime = pd.to_datetime(start_date)
                            end_datetime = pd.to_datetime(end_date)

                            if st.button("📊 Calcola Performance", type="primary"):
                                performance_df = calculate_technician_performance(archivio_df_perf, start_datetime, end_datetime)
                                st.session_state['performance_results'] = {
                                    'df': performance_df,
                                    'start_date': start_datetime,
                                    'end_date': end_datetime
                                }

                            if 'performance_results' in st.session_state and not st.session_state['performance_results']['df'].empty:
                                results = st.session_state['performance_results']
                                performance_df = results['df']

                                st.markdown("---")
                                st.markdown("### Riepilogo Performance del Team")

                                total_interventions_team = performance_df['Totale Interventi'].sum()
                                total_rushed_reports_team = performance_df['Report Sbrigativi'].sum()
                                total_completed_interventions = (performance_df['Tasso Completamento (%)'].astype(float) / 100) * performance_df['Totale Interventi']
                                avg_completion_rate_team = (total_completed_interventions.sum() / total_interventions_team) * 100 if total_interventions_team > 0 else 0
                                
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Totale Interventi", f"{total_interventions_team}")
                                c2.metric("Tasso Completamento Medio", f"{avg_completion_rate_team:.1f}%")
                                c3.metric("Report Sbrigativi", f"{total_rushed_reports_team}")

                                st.markdown("#### Dettaglio Performance per Tecnico")
                                for index, row in performance_df.iterrows():
                                    st.write(f"**Tecnico:** {index}")
                                    st.dataframe(row.to_frame().T)
                                    if st.button(f"Vedi Dettaglio Interventi di {index}", key=f"detail_{index}"):
                                        st.session_state['detail_technician'] = index
                                        st.session_state['detail_start_date'] = results['start_date']
                                        st.session_state['detail_end_date'] = results['end_date']
                                        st.rerun()

                    with admin_tabs[1]: # Revisione Conoscenze
                        st.markdown("### 🧠 Revisione Voci del Knowledge Core")
                        unreviewed_entries = learning_module.load_unreviewed_knowledge()
                        pending_entries = [e for e in unreviewed_entries if e.get('stato') == 'in attesa di revisione']

                        if not pending_entries:
                            st.success("🎉 Nessuna nuova voce da revisionare!")
                        else:
                            st.info(f"Ci sono {len(pending_entries)} nuove voci suggerite dai tecnici da revisionare.")

                        for i, entry in enumerate(pending_entries):
                            with st.expander(f"**Voce ID:** `{entry['id']}` - **Attività:** {entry['attivita_collegata']}", expanded=i==0):
                                st.markdown(f"*Suggerito da: **{entry['suggerito_da']}** il {datetime.datetime.fromisoformat(entry['data_suggerimento']).strftime('%d/%m/%Y %H:%M')}*")
                                st.markdown(f"*PdL di riferimento: `{entry['pdl']}`*")

                                st.write("**Dettagli del report compilato:**")
                                st.json(entry['dettagli_report'])

                                st.markdown("---")
                                st.markdown("**Azione di Integrazione**")

                                col1, col2 = st.columns(2)
                                with col1:
                                    new_equipment_key = st.text_input("Nuova Chiave Attrezzatura (es. 'motore_elettrico')", key=f"key_{entry['id']}")
                                    new_display_name = st.text_input("Nome Visualizzato (es. 'Motore Elettrico')", key=f"disp_{entry['id']}")
                                with col2:
                                    if st.button("✅ Integra nel Knowledge Core", key=f"integrate_{entry['id']}", type="primary"):
                                        if new_equipment_key and new_display_name:
                                            first_question = {
                                                "id": "sintomo_iniziale",
                                                "text": "Qual era il sintomo principale?",
                                                "options": {k.lower().replace(' ', '_'): v for k, v in entry['dettagli_report'].items()}
                                            }
                                            details = {
                                                "equipment_key": new_equipment_key,
                                                "display_name": new_display_name,
                                                "new_question": first_question
                                            }
                                            result = learning_module.integrate_knowledge(entry['id'], details)
                                            if result.get("success"):
                                                st.success(f"Voce '{entry['id']}' integrata con successo!")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error(f"Errore integrazione: {result.get('error')}")
                                        else:
                                            st.warning("Per integrare, fornisci sia la chiave che il nome visualizzato.")

                    with admin_tabs[2]: # Crea Nuovo Turno
                        with st.form("new_shift_form", clear_on_submit=True):
                            st.subheader("Dettagli Nuovo Turno")
                            tipo_turno = st.selectbox("Tipo Turno", ["Assistenza", "Straordinario"])
                            desc_turno = st.text_input("Descrizione Turno (es. 'Mattina', 'Straordinario Sabato')")
                            data_turno = st.date_input("Data Turno")
                            col1, col2 = st.columns(2)
                            with col1:
                                ora_inizio = st.time_input("Orario Inizio", datetime.time(8, 0))
                            with col2:
                                ora_fine = st.time_input("Orario Fine", datetime.time(17, 0))
                            col3, col4 = st.columns(2)
                            with col3:
                                posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1)
                            with col4:
                                posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1)

                            submitted = st.form_submit_button("Crea Turno")
                            if submitted:
                                if not desc_turno:
                                    st.error("La descrizione non può essere vuota.")
                                else:
                                    new_id = f"T_{int(datetime.datetime.now().timestamp())}"
                                    nuovo_turno = pd.DataFrame([{'ID_Turno': new_id, 'Descrizione': desc_turno, 'Data': pd.to_datetime(data_turno), 'OrarioInizio': ora_inizio.strftime('%H:%M'), 'OrarioFine': ora_fine.strftime('%H:%M'), 'PostiTecnico': posti_tech, 'PostiAiutante': posti_aiut, 'Tipo': tipo_turno}])
                                    gestionale_data['turni'] = pd.concat([gestionale_data['turni'], nuovo_turno], ignore_index=True)
                                    df_contatti = gestionale_data.get('contatti')
                                    if df_contatti is not None:
                                        utenti_da_notificare = df_contatti['Nome Cognome'].tolist()
                                        messaggio = f"📢 Nuovo turno disponibile: '{desc_turno}' il {pd.to_datetime(data_turno).strftime('%d/%m/%Y')}."
                                        for utente in utenti_da_notificare:
                                            crea_notifica(gestionale_data, utente, messaggio)
                                    if salva_gestionale_async(gestionale_data):
                                        st.success(f"Turno '{desc_turno}' creato con successo! Notifiche inviate.")
                                        st.toast("Tutti i tecnici sono stati notificati!")
                                        st.rerun()
                                    else:
                                        st.error("Errore nel salvataggio del nuovo turno.")

                    with admin_tabs[3]: # Gestione Account
                        render_gestione_account(gestionale_data)


# --- GESTIONE LOGIN ---

# Initialize session state keys if they don't exist
keys_to_initialize = {
    'login_state': 'password', # 'password', 'setup_2fa', 'verify_2fa', 'logged_in'
    'authenticated_user': None,
    'ruolo': None,
    'debriefing_task': None,
    'temp_user_for_2fa': None,
    '2fa_secret': None
}
for key, default_value in keys_to_initialize.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Prova a caricare una sessione esistente all'avvio
if not st.session_state.get('authenticated_user'):
    load_session()
    if st.session_state.get('authenticated_user'):
        st.session_state.login_state = 'logged_in'


# --- UI LOGIC ---

if st.session_state.login_state == 'logged_in':
    main_app(st.session_state.authenticated_user, st.session_state.ruolo)

else:
    st.set_page_config(layout="centered", page_title="Login")
    st.title("Accesso Area Report")
    
    gestionale = carica_gestionale()
    if not gestionale or 'contatti' not in gestionale:
        st.error("Errore critico: impossibile caricare i dati degli utenti.")
        st.stop()

    df_contatti = gestionale['contatti']

    if st.session_state.login_state == 'password':
        with st.form("login_form"):
            username_inserito = st.text_input("Nome Utente (Cognome)")
            password_inserita = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Accedi")

            if submitted:
                if not username_inserito or not password_inserita:
                    st.warning("Per favore, inserisci nome utente e password.")
                else:
                    status, user_data = authenticate_user(username_inserito, password_inserita, df_contatti)

                    if status == "2FA_REQUIRED":
                        st.session_state.login_state = 'verify_2fa'
                        st.session_state.temp_user_for_2fa = user_data # Salva il nome utente
                        st.rerun()
                    elif status == "2FA_SETUP_REQUIRED":
                        st.session_state.login_state = 'setup_2fa'
                        st.session_state.temp_user_for_2fa, st.session_state.ruolo = user_data
                        st.rerun()
                    elif status == "SUCCESS":
                        nome_completo, ruolo = user_data
                        st.session_state.login_state = 'logged_in'
                        st.session_state.authenticated_user = nome_completo
                        st.session_state.ruolo = ruolo
                        save_session(nome_completo, ruolo)
                        st.rerun()
                    else:
                        st.error("Credenziali non valide.")

    elif st.session_state.login_state == 'setup_2fa':
        st.subheader("Configurazione Sicurezza Account (2FA)")
        st.info("Per una maggiore sicurezza, è necessario configurare la verifica in due passaggi.")

        if not st.session_state.get('2fa_secret'):
            st.session_state['2fa_secret'] = generate_2fa_secret()

        secret = st.session_state['2fa_secret']
        user_to_setup = st.session_state['temp_user_for_2fa']

        uri = get_provisioning_uri(user_to_setup, secret)
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
                    user_idx = df_contatti[df_contatti['Nome Cognome'] == user_to_setup].index[0]
                    # Assicura che la colonna esista prima di scrivere
                    if '2FA_Secret' not in df_contatti.columns:
                        df_contatti['2FA_Secret'] = None
                    df_contatti.loc[user_idx, '2FA_Secret'] = secret

                    if salva_gestionale_async(gestionale):
                        st.success("Configurazione 2FA completata con successo! Accesso in corso...")
                        st.session_state.login_state = 'logged_in'
                        st.session_state.authenticated_user = user_to_setup
                        # il ruolo è già in sessione
                        save_session(user_to_setup, st.session_state.ruolo)
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio della configurazione. Riprova.")
                else:
                    st.error("Codice non valido. Riprova.")

    elif st.session_state.login_state == 'verify_2fa':
        st.subheader("Verifica in Due Passaggi")
        user_to_verify = st.session_state.temp_user_for_2fa
        user_row = df_contatti[df_contatti['Nome Cognome'] == user_to_verify].iloc[0]
        secret = user_row['2FA_Secret']
        ruolo = user_row['Ruolo']

        with st.form("verify_2fa_login"):
            code = st.text_input(f"Ciao {user_to_verify.split()[0]}, inserisci il codice dalla tua app di autenticazione")
            submitted = st.form_submit_button("Verifica")

            if submitted:
                if verify_2fa_code(secret, code):
                    st.success("Codice corretto! Accesso in corso...")
                    st.session_state.login_state = 'logged_in'
                    st.session_state.authenticated_user = user_to_verify
                    st.session_state.ruolo = ruolo
                    save_session(user_to_verify, ruolo)
                    st.rerun()
                else:
                    st.error("Codice non valido. Riprova.")
