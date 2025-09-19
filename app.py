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
import pythoncom # Necessario per la gestione di Outlook in un thread
import learning_module

# --- CONFIGURAZIONE ---
path_giornaliera_base = r'\\192.168.11.251\Database_Tecnico_SMI\Giornaliere\Giornaliere 2025'
PATH_GESTIONALE = r'C:\Users\Coemi\Desktop\SCRIPT\progetto_questionario_attivita\Gestionale_Tecnici.xlsx'
path_storico_db = r'\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\Database_Report_Attivita.xlsm'
NOME_FOGLIO_RISPOSTE = "Report Attività Giornaliera (Risposte)"
PATH_KNOWLEDGE_CORE = "knowledge_core.json"
EMAIL_DESTINATARIO = "gianky.allegretti@gmail.com"

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

@st.cache_data
def carica_knowledge_core():
    try:
        with open(PATH_KNOWLEDGE_CORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Errore critico: File '{PATH_KNOWLEDGE_CORE}' non trovato.")
        return None
    except json.JSONDecodeError:
        st.error(f"Errore critico: Il file '{PATH_KNOWLEDGE_CORE}' non è un JSON valido.")
        return None

#@st.cache_data
def carica_gestionale():
    try:
        xls = pd.ExcelFile(PATH_GESTIONALE)
        data = {
            'contatti': pd.read_excel(xls, sheet_name='Contatti'),
            'turni': pd.read_excel(xls, sheet_name='TurniDisponibili'),
            'prenotazioni': pd.read_excel(xls, sheet_name='Prenotazioni'),
            'sostituzioni': pd.read_excel(xls, sheet_name='SostituzioniPendenti')
        }

        # Handle 'Tipo' column in 'turni' DataFrame for backward compatibility
        if 'Tipo' not in data['turni'].columns:
            data['turni']['Tipo'] = 'Assistenza'
        data['turni']['Tipo'].fillna('Assistenza', inplace=True)

        required_notification_cols = ['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione']

        if 'Notifiche' in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name='Notifiche')
            # Sanitize column names to remove leading/trailing whitespace
            df.columns = df.columns.str.strip()

            # Check for missing columns and add them if necessary
            for col in required_notification_cols:
                if col not in df.columns:
                    df[col] = pd.NA
            data['notifiche'] = df
        else:
            data['notifiche'] = pd.DataFrame(columns=required_notification_cols)

        return data
    except Exception as e:
        st.error(f"Errore critico nel caricamento del file Gestionale_Tecnici.xlsx: {e}")
        return None

def salva_gestionale(data):
    try:
        with pd.ExcelWriter(PATH_GESTIONALE, engine='openpyxl') as writer:
            data['contatti'].to_excel(writer, sheet_name='Contatti', index=False)
            data['turni'].to_excel(writer, sheet_name='TurniDisponibili', index=False)
            data['prenotazioni'].to_excel(writer, sheet_name='Prenotazioni', index=False)
            data['sostituzioni'].to_excel(writer, sheet_name='SostituzioniPendenti', index=False)
            if 'notifiche' in data:
                data['notifiche'].to_excel(writer, sheet_name='Notifiche', index=False)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore durante il salvataggio del file gestionale: {e}")
        return False

def leggi_notifiche(gestionale_data, utente):
    df_notifiche = gestionale_data.get('notifiche')

    required_cols = ['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione']
    if df_notifiche is None or df_notifiche.empty:
        return pd.DataFrame(columns=required_cols)

    user_notifiche = df_notifiche[df_notifiche['Destinatario'] == utente].copy()

    if user_notifiche.empty:
        return user_notifiche

    user_notifiche['Timestamp'] = pd.to_datetime(user_notifiche['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    return user_notifiche.sort_values(by='Timestamp', ascending=False)

def crea_notifica(gestionale_data, destinatario, messaggio, link_azione=""):
    if 'notifiche' not in gestionale_data:
        gestionale_data['notifiche'] = pd.DataFrame(columns=['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione'])

    new_id = f"N_{int(datetime.datetime.now().timestamp())}"
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    nuova_notifica = pd.DataFrame([{
        'ID_Notifica': new_id,
        'Timestamp': timestamp,
        'Destinatario': destinatario,
        'Messaggio': messaggio,
        'Stato': 'non letta',
        'Link_Azione': link_azione
    }])

    gestionale_data['notifiche'] = pd.concat([gestionale_data['notifiche'], nuova_notifica], ignore_index=True)
    return True

def segna_notifica_letta(gestionale_data, id_notifica):
    if 'notifiche' not in gestionale_data or gestionale_data['notifiche'].empty:
        return False

    df_notifiche = gestionale_data['notifiche']
    idx = df_notifiche[df_notifiche['ID_Notifica'] == id_notifica].index

    if not idx.empty:
        df_notifiche.loc[idx, 'Stato'] = 'letta'
        return True
    return False

def carica_archivio_completo():
    try:
        df = pd.read_excel(path_storico_db)
        df['Data_Riferimento_dt'] = pd.to_datetime(df['Data_Riferimento'], errors='coerce')
        df.dropna(subset=['Data_Riferimento_dt'], inplace=True)
        df.sort_values(by='Data_Compilazione', ascending=True, inplace=True)
        df.drop_duplicates(subset=['PdL', 'Tecnico', 'Data_Riferimento'], keep='last', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def verifica_password(utente_da_url, password_inserita, df_contatti):
    if df_contatti is None or df_contatti.empty: return None, None
    for _, riga in df_contatti.iterrows():
        nome_completo = str(riga['Nome Cognome']).strip()
        user_param_corretto = nome_completo.split()[-1]
        if "Garro" in nome_completo: user_param_corretto = "Garro L"
        if utente_da_url.lower() == user_param_corretto.lower() and str(password_inserita) == str(riga['Password']):
            return nome_completo, riga.get('Ruolo', 'Tecnico')
    return None, None

def trova_attivita(utente_completo, giorno, mese, anno):
    try:
        path_giornaliera_mensile = os.path.join(path_giornaliera_base, f"Giornaliera {mese:02d}-{anno}.xlsm")
        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=str(giorno), engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45].copy()
        
        # BUG FIX: Raccoglie tutte le righe corrispondenti, non solo la prima
        righe_utente = []
        for _, riga in df_range.iterrows():
            nome_in_giornaliera = str(riga[5]).strip()
            if not nome_in_giornaliera or nome_in_giornaliera.lower() == 'nan': continue
            parts_completo = utente_completo.lower().split()
            if nome_in_giornaliera.lower() in ' '.join(parts_completo):
                righe_utente.append(riga) # Aggiunge la riga e continua a cercare

        if not righe_utente: return []
        
        df_utente = pd.DataFrame(righe_utente)
        df_storico_db = carica_archivio_completo()
        lista_attivita_finale = []

        for _, riga in df_utente.iterrows():
            pdl_text, desc_text = str(riga[9]), str(riga[6])
            if pd.isna(pdl_text) or pd.isna(desc_text): continue
            lista_pdl = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
            lista_descrizioni = [line.strip() for line in desc_text.splitlines() if line.strip()]
            for pdl, desc in zip(lista_pdl, lista_descrizioni):
                storico_df_pdl = df_storico_db[df_storico_db['PdL'] == pdl].copy() if not df_storico_db.empty else pd.DataFrame()
                if not storico_df_pdl.empty:
                    storico_df_pdl['Data_Riferimento'] = storico_df_pdl['Data_Riferimento_dt'].dt.strftime('%d/%m/%Y')
                    storico = storico_df_pdl.to_dict('records')
                else:
                    storico = []
                lista_attivita_finale.append({'pdl': pdl, 'attivita': desc, 'storico': storico})
        return lista_attivita_finale
    except FileNotFoundError: return []
    except Exception as e: st.error(f"Errore lettura giornaliera: {e}"); return []


# --- FUNZIONI DI BUSINESS ---
def invia_email_con_outlook(subject, html_body):
    pythoncom.CoInitialize()
    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = EMAIL_DESTINATARIO
        mail.CC = "francesco.millo@coemi.it"
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Send()
    except Exception as e:
        st.warning(f"Impossibile inviare l'email con Outlook: {e}. Assicurati che Outlook sia installato e in esecuzione.")
    finally:
        pythoncom.CoUninitialize()

def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    try:
        foglio_risposte = client.open(NOME_FOGLIO_RISPOSTE).sheet1
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dati_formattati = [timestamp, nome_completo, dati_da_scrivere['descrizione'], dati_da_scrivere['report'], dati_da_scrivere['stato'], data_riferimento.strftime('%d/%m/%Y')]
        
        if row_index:
            foglio_risposte.update(f'A{row_index}:F{row_index}', [dati_formattati])
            azione = "aggiornato"
        else:
            foglio_risposte.append_row(dati_formattati)
            row_index = len(foglio_risposte.get_all_values())
            azione = "inviato"

        titolo_email = f"Report Attività {azione.upper()} da: {nome_completo}"
        report_html = dati_da_scrivere['report'].replace('\n', '<br>')
        html_body = f"""
        <html>
        <head>
        <style>
            body {{ font-family: Calibri, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            .report-content {{ white-space: pre-wrap; word-wrap: break-word; }}
        </style>
        </head>
        <body>
        <h2>Riepilogo Report Attività</h2>
        <p>Un report è stato <strong>{azione}</strong> dal tecnico {nome_completo}.</p>
        <table>
            <tr>
                <th>Data di Riferimento Attività</th>
                <td>{data_riferimento.strftime('%d/%m/%Y')}</td>
            </tr>
            <tr>
                <th>Data e Ora Invio Report</th>
                <td>{timestamp}</td>
            </tr>
            <tr>
                <th>Tecnico</th>
                <td>{nome_completo}</td>
            </tr>
            <tr>
                <th>Attività</th>
                <td>{dati_da_scrivere['descrizione']}</td>
            </tr>
            <tr>
                <th>Stato Finale</th>
                <td><b>{dati_da_scrivere['stato']}</b></td>
            </tr>
            <tr>
                <th>Report Compilato</th>
                <td class="report-content">{report_html}</td>
            </tr>
        </table>
        </body>
        </html>
        """
        invia_email_con_outlook(titolo_email, html_body)
        return row_index
    except Exception as e:
        st.error(f"Errore salvataggio GSheets: {e}")
        return None

# --- LOGICA DI BUSINESS PER I TURNI ---
def prenota_turno_logic(gestionale_data, utente, turno_id, ruolo_scelto):
    df_turni, df_prenotazioni = gestionale_data['turni'], gestionale_data['prenotazioni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    posti_tecnico, posti_aiutante = int(float(turno_info['PostiTecnico'])), int(float(turno_info['PostiAiutante']))
    prenotazioni_per_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
    tecnici_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Tecnico'])
    aiutanti_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Aiutante'])
    if ruolo_scelto == 'Tecnico' and tecnici_prenotati < posti_tecnico:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = pd.concat([df_prenotazioni, pd.DataFrame([nuova_riga])], ignore_index=True)
        st.success("Turno prenotato come Tecnico!"); return True
    elif ruolo_scelto == 'Aiutante' and aiutanti_prenotati < posti_aiutante:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = pd.concat([df_prenotazioni, pd.DataFrame([nuova_riga])], ignore_index=True)
        st.success("Turno prenotato come Aiutante!"); return True
    else:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!"); return False

def cancella_prenotazione_logic(gestionale_data, utente, turno_id):
    index_to_drop = gestionale_data['prenotazioni'][(gestionale_data['prenotazioni']['ID_Turno'] == turno_id) & (gestionale_data['prenotazioni']['Nome Cognome'] == utente)].index
    if not index_to_drop.empty:
        gestionale_data['prenotazioni'].drop(index_to_drop, inplace=True)
        st.success("Prenotazione cancellata."); return True
    st.error("Prenotazione non trovata."); return False

def richiedi_sostituzione_logic(gestionale_data, richiedente, ricevente, turno_id):
    nuova_richiesta = pd.DataFrame([{'ID_Richiesta': f"S_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Richiedente': richiedente, 'Ricevente': ricevente, 'Timestamp': datetime.datetime.now()}])
    gestionale_data['sostituzioni'] = pd.concat([gestionale_data['sostituzioni'], nuova_richiesta], ignore_index=True)

    messaggio = f"Hai una nuova richiesta di sostituzione da {richiedente} per il turno {turno_id}."
    crea_notifica(gestionale_data, ricevente, messaggio)

    st.success(f"Richiesta di sostituzione inviata a {ricevente}.")
    st.toast("Richiesta inviata! Il collega riceverà una notifica.")
    return True

def rispondi_sostituzione_logic(gestionale_data, id_richiesta, utente_che_risponde, accettata):
    sostituzioni_df = gestionale_data['sostituzioni']
    richiesta_index = sostituzioni_df[sostituzioni_df['ID_Richiesta'] == id_richiesta].index
    if richiesta_index.empty:
        st.error("Richiesta non più valida.")
        return False

    richiesta = sostituzioni_df.loc[richiesta_index[0]]
    richiedente = richiesta['Richiedente']
    turno_id = richiesta['ID_Turno']

    if accettata:
        messaggio = f"{utente_che_risponde} ha ACCETTATO la tua richiesta di cambio per il turno {turno_id}."
    else:
        messaggio = f"{utente_che_risponde} ha RIFIUTATO la tua richiesta di cambio per il turno {turno_id}."
    crea_notifica(gestionale_data, richiedente, messaggio)

    gestionale_data['sostituzioni'].drop(richiesta_index, inplace=True)
    
    if not accettata:
        st.info("Hai rifiutato la richiesta.")
        st.toast("Risposta inviata. Il richiedente è stato notificato.")
        return True

    # Logic for accepted request
    prenotazioni_df = gestionale_data['prenotazioni']
    idx_richiedente_originale = prenotazioni_df[(prenotazioni_df['ID_Turno'] == turno_id) & (prenotazioni_df['Nome Cognome'] == richiedente)].index

    if not idx_richiedente_originale.empty:
        prenotazioni_df.loc[idx_richiedente_originale, 'Nome Cognome'] = utente_che_risponde
        st.success("Sostituzione (subentro) effettuata con successo!")
        st.toast("Sostituzione effettuata! Il richiedente è stato notificato.")
        return True

    st.error("Errore: la prenotazione originale del richiedente non è stata trovata per lo scambio.")
    return False

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
    archivio_df['Data_Riferimento_dt'] = pd.to_datetime(archivio_df['Data_Riferimento'], format='%d/%m/%Y', errors='coerce')
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
                intervento['data_dt'] = pd.to_datetime(intervento.get('Data_Riferimento'), errors='coerce')
            
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

def disegna_sezione_attivita(lista_attivita, section_key):
    if f"completed_tasks_{section_key}" not in st.session_state:
        st.session_state[f"completed_tasks_{section_key}"] = []

    completed_pdls = {task['pdl'] for task in st.session_state[f"completed_tasks_{section_key}"] }
    attivita_da_fare = [task for task in lista_attivita if task['pdl'] not in completed_pdls]

    st.subheader("📝 Attività da Compilare")
    if not attivita_da_fare:
        st.info("Tutte le attività per questa sezione sono state compilate.")
    
    for i, task in enumerate(attivita_da_fare):
        with st.container(border=True):
            st.markdown(f"**PdL `{task['pdl']}`** - {task['attivita']}")
            
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
            col1, col2 = st.columns(2)
            if col1.button("✍️ Compila Report Guidato (IA)", key=f"guide_{section_key}_{i}"):
                st.session_state.debriefing_task = {**task, "section_key": section_key}
                st.session_state.report_mode = 'guided'
                st.rerun()
            if col2.button("📝 Compila Report Manuale", key=f"manual_{section_key}_{i}"):
                st.session_state.debriefing_task = {**task, "section_key": section_key}
                st.session_state.report_mode = 'manual'
                st.rerun()
    
    st.divider()

    if st.session_state[f"completed_tasks_{section_key}"]:
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
                            salva_gestionale(gestionale_data)
                            st.rerun()
                st.divider()

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
                for _, p in prenotazioni_turno.iterrows():
                    st.write(f"- {p['Nome Cognome']} (*{p['RuoloOccupato']}*)")

            st.markdown("---")

            if ruolo == "Amministratore":
                if st.button("✏️ Modifica Turno", key=f"edit_{turno['ID_Turno']}_{key_suffix}"):
                    st.session_state['editing_turno_id'] = turno['ID_Turno']
                    st.rerun()
                st.markdown("---")

            prenotazione_utente = prenotazioni_turno[prenotazioni_turno['Nome Cognome'] == nome_utente_autenticato]

            if not prenotazione_utente.empty:
                st.success("Sei prenotato per questo turno.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Cancella Prenotazione", key=f"del_{turno['ID_Turno']}_{key_suffix}"):
                        if cancella_prenotazione_logic(gestionale, nome_utente_autenticato, turno['ID_Turno']):
                            salva_gestionale(gestionale); st.rerun()
                with col2:
                    if st.button("Chiedi Sostituzione", key=f"ask_{turno['ID_Turno']}_{key_suffix}"):
                        st.session_state['sostituzione_turno_id'] = turno['ID_Turno']; st.rerun()
            else:
                opzioni = []
                if tecnici_prenotati < posti_tecnico: opzioni.append("Tecnico")
                if aiutanti_prenotati < posti_aiutante: opzioni.append("Aiutante")
                if opzioni:
                    ruolo_scelto = st.selectbox("Prenota come:", opzioni, key=f"sel_{turno['ID_Turno']}_{key_suffix}")
                    if st.button("Conferma Prenotazione", key=f"add_{turno['ID_Turno']}_{key_suffix}"):
                        if prenota_turno_logic(gestionale, nome_utente_autenticato, turno['ID_Turno'], ruolo_scelto):
                            salva_gestionale(gestionale); st.rerun()
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
                        salva_gestionale(gestionale); del st.session_state['sostituzione_turno_id']; st.rerun()

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


# --- APPLICAZIONE STREAMLIT PRINCIPALE ---
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

        # 2. Calcola le modifiche al personale
        personale_originale = set(personale_nel_turno['Nome Cognome'].tolist())
        personale_nuovo = set(tecnici_selezionati + aiutanti_selezionati)

        personale_rimosso = personale_originale - personale_nuovo

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
        if salva_gestionale(gestionale_data):
            st.success("Turno aggiornato con successo!")
            st.toast("Le modifiche sono state salvate.")
            del st.session_state['editing_turno_id']
            st.rerun()
        else:
            st.error("Si è verificato un errore durante il salvataggio delle modifiche.")

def main_app(nome_utente_autenticato, ruolo):
    st.set_page_config(layout="wide", page_title="Report Attività")

    gestionale_data = carica_gestionale()

    if st.session_state.get('editing_turno_id'):
        render_edit_shift_form(gestionale_data)
    elif st.session_state.get('debriefing_task'):
        knowledge_core = carica_knowledge_core()
        if knowledge_core:
            render_debriefing_ui(knowledge_core, nome_utente_autenticato, datetime.date.today(), autorizza_google())
    else:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.title(f"Report Attività")
            st.header(f"Ciao, {nome_utente_autenticato}!")
            st.caption(f"Ruolo: {ruolo}")
        with col2:
            st.write("") # Spacer
            st.write("") # Spacer
            user_notifications = leggi_notifiche(gestionale_data, nome_utente_autenticato)
            render_notification_center(user_notifications, gestionale_data)

        oggi = datetime.date.today()
        giorno_precedente = oggi - datetime.timedelta(days=1)
        if oggi.weekday() == 0: giorno_precedente = oggi - datetime.timedelta(days=3)
        elif oggi.weekday() == 6: giorno_precedente = oggi - datetime.timedelta(days=2)
        
        if ruolo in ["Amministratore", "Tecnico"]:
            attivita_pianificate_ieri = trova_attivita(nome_utente_autenticato, giorno_precedente.day, giorno_precedente.month, giorno_precedente.year)
            num_attivita_mancanti = 0
            if attivita_pianificate_ieri:
                archivio_df = carica_archivio_completo()
                pdl_compilati_ieri = set(archivio_df[(archivio_df['Tecnico'] == nome_utente_autenticato) & (archivio_df['Data_Riferimento_dt'].dt.date == giorno_precedente)]['PdL']) if not archivio_df.empty else set()
                num_attivita_mancanti = len(attivita_pianificate_ieri) - len(pdl_compilati_ieri)
            if num_attivita_mancanti > 0:
                st.warning(f"**Promemoria:** Hai **{num_attivita_mancanti} attività** del giorno precedente non compilate.")

        lista_tab = ["Attività di Oggi", "Attività Giorno Precedente", "Ricerca nell'Archivio", "Gestione Turni"]
        if ruolo == "Amministratore":
            lista_tab.append("Dashboard Admin")
        
        tabs = st.tabs(lista_tab)
        
        with tabs[0]:
            st.header(f"Attività del {oggi.strftime('%d/%m/%Y')}")
            lista_attivita = trova_attivita(nome_utente_autenticato, oggi.day, oggi.month, oggi.year)
            disegna_sezione_attivita(lista_attivita, "today")
        
        with tabs[1]:
            st.header(f"Recupero attività del {giorno_precedente.strftime('%d/%m/%Y')}")
            lista_attivita_ieri_totale = trova_attivita(nome_utente_autenticato, giorno_precedente.day, giorno_precedente.month, giorno_precedente.year)
            archivio_df = carica_archivio_completo()
            pdl_compilati_ieri = set()
            if not archivio_df.empty:
                report_compilati = archivio_df[(archivio_df['Tecnico'] == nome_utente_autenticato) & (archivio_df['Data_Riferimento_dt'].dt.date == giorno_precedente)]
                pdl_compilati_ieri = set(report_compilati['PdL'])
            
            attivita_da_recuperare = [task for task in lista_attivita_ieri_totale if task['pdl'] not in pdl_compilati_ieri]
            disegna_sezione_attivita(attivita_da_recuperare, "yesterday")

        with tabs[2]:
            st.subheader("Ricerca nell'Archivio")
            archivio_df = carica_archivio_completo()
            if archivio_df.empty:
                st.warning("L'archivio è vuoto o non caricabile.")
            else:
                col1, col2, col3 = st.columns(3)
                with col1: pdl_search = st.text_input("Filtra per PdL", key="pdl_search")
                with col2: desc_search = st.text_input("Filtra per Descrizione", key="desc_search")
                with col3:
                    lista_tecnici = sorted(list(archivio_df['Tecnico'].dropna().unique()))
                    tec_search = st.multiselect("Filtra per Tecnico/i", options=lista_tecnici, key="tec_search")
                
                risultati_df = archivio_df.copy()
                if pdl_search: risultati_df = risultati_df[risultati_df['PdL'].astype(str).str.contains(pdl_search, case=False, na=False)]
                if desc_search: risultati_df = risultati_df[risultati_df['Descrizione'].astype(str).str.contains(desc_search, case=False, na=False)]
                if tec_search: risultati_df = risultati_df[risultati_df['Tecnico'].isin(tec_search)]
                
                if not risultati_df.empty:
                    pdl_unici_df = risultati_df.sort_values(by='Data_Riferimento_dt', ascending=False).drop_duplicates(subset=['PdL'], keep='first')
                    st.info(f"Trovati {len(risultati_df)} interventi, raggruppati in {len(pdl_unici_df)} PdL unici.")
                    for _, riga_pdl in pdl_unici_df.iterrows():
                        pdl_corrente = riga_pdl['PdL']
                        descrizione_recente = riga_pdl.get('Descrizione', '')
                        with st.expander(f"**PdL {pdl_corrente}** | *{str(descrizione_recente)[:60]}...*"):
                            interventi_per_pdl_df = risultati_df[risultati_df['PdL'] == pdl_corrente].sort_values(by='Data_Riferimento_dt', ascending=False)
                            visualizza_storico_organizzato(interventi_per_pdl_df.to_dict('records'), pdl_corrente)
                else:
                    st.info("Nessun record trovato.")

        with tabs[3]:
            st.subheader("Gestione Turni Personale")
            if gestionale_data:
                turni_disponibili_tab, sostituzioni_tab = st.tabs(["📅 Turni Disponibili", "🔄 Gestione Sostituzioni"])

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
                                    if rispondi_sostituzione_logic(gestionale, richiesta['ID_Richiesta'], nome_utente_autenticato, True):
                                        salva_gestionale(gestionale); st.rerun()
                            with c2:
                                if st.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                                    if rispondi_sostituzione_logic(gestionale, richiesta['ID_Richiesta'], nome_utente_autenticato, False):
                                        salva_gestionale(gestionale); st.rerun()
                    st.divider()
                    st.markdown("#### 📤 Richieste Inviate")
                    richieste_inviate = df_sostituzioni[df_sostituzioni['Richiedente'] == nome_utente_autenticato]
                    if richieste_inviate.empty: st.info("Nessuna richiesta di sostituzione inviata.")
                    for _, richiesta in richieste_inviate.iterrows():
                        st.markdown(f"- Richiesta inviata a **{richiesta['Ricevente']}** per il turno **{richiesta['ID_Turno']}**.")
        
        if len(tabs) > 4 and ruolo == "Amministratore":
            with tabs[4]:
                st.subheader("Dashboard di Controllo")

                # Se è stata selezionata la vista di dettaglio, mostrala
                if st.session_state.get('detail_technician'):
                    render_technician_detail_view()
                else:
                    # Altrimenti, mostra le tab principali della dashboard
                    # Logic to control expander state
                    expand_form = True
                    if st.session_state.get('shift_form_submitted', False):
                        expand_form = False
                        st.session_state.shift_form_submitted = False # Reset for next interaction

                    with st.expander("➕ Crea Nuovo Turno", expanded=expand_form):
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
                                    nuovo_turno = pd.DataFrame([{
                                        'ID_Turno': new_id,
                                        'Descrizione': desc_turno,
                                        'Data': pd.to_datetime(data_turno),
                                        'OrarioInizio': ora_inizio.strftime('%H:%M'),
                                        'OrarioFine': ora_fine.strftime('%H:%M'),
                                        'PostiTecnico': posti_tech,
                                        'PostiAiutante': posti_aiut,
                                        'Tipo': tipo_turno
                                    }])
                                    gestionale_data['turni'] = pd.concat([gestionale_data['turni'], nuovo_turno], ignore_index=True)

                                    # Logica di notifica per nuovo turno
                                    df_contatti = gestionale_data.get('contatti')
                                    if df_contatti is not None:
                                        utenti_da_notificare = df_contatti['Nome Cognome'].tolist()
                                        messaggio = f"📢 Nuovo turno disponibile: '{desc_turno}' il {pd.to_datetime(data_turno).strftime('%d/%m/%Y')}."
                                        for utente in utenti_da_notificare:
                                            crea_notifica(gestionale_data, utente, messaggio)

                                    if salva_gestionale(gestionale_data):
                                        st.session_state.shift_form_submitted = True
                                        st.success(f"Turno '{desc_turno}' creato con successo! Notifiche inviate.")
                                        st.toast("Tutti i tecnici sono stati notificati!")
                                        st.rerun()
                                    else:
                                        st.error("Errore nel salvataggio del nuovo turno.")

                    st.divider()

                    admin_tabs = st.tabs(["Performance Team", "Revisione Conoscenze"])

                    with admin_tabs[0]:
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

                    with admin_tabs[1]:
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


# --- GESTIONE LOGIN ---
if 'authenticated_user' not in st.session_state:
    st.session_state.authenticated_user = None
    st.session_state.ruolo = None
    st.session_state.debriefing_task = None

if st.session_state.authenticated_user:
    main_app(st.session_state.authenticated_user, st.session_state.ruolo)
else:
    st.set_page_config(layout="centered", page_title="Login")
    st.title("Accesso Area Report")
    utente_url = st.query_params.get("user")
    if not utente_url: st.error("ERRORE: Link non valido."); st.stop()
    
    password_inserita = st.text_input(f"Password per {utente_url}", type="password")
    if st.button("Accedi"):
        gestionale = carica_gestionale()
        if gestionale and 'contatti' in gestionale:
            nome, ruolo = verifica_password(utente_url, password_inserita, gestionale['contatti'])
            if nome:
                st.session_state.authenticated_user = nome
                st.session_state.ruolo = ruolo
                st.rerun()
            else:
                st.error("Credenziali non valide.")
        else:
            st.error("Impossibile caricare dati di login.")
