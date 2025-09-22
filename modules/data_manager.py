import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading
import openpyxl

import config
from modules.email_sender import invia_email_con_outlook_async

@st.cache_data
def carica_knowledge_core():
    try:
        with open(config.PATH_KNOWLEDGE_CORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Errore critico: File '{config.PATH_KNOWLEDGE_CORE}' non trovato.")
        return None
    except json.JSONDecodeError:
        st.error(f"Errore critico: Il file '{config.PATH_KNOWLEDGE_CORE}' non è un JSON valido.")
        return None

def carica_gestionale():
    with config.EXCEL_LOCK:
        try:
            path_gestionale = st.secrets["paths"]["PATH_GESTIONALE"]
            xls = pd.ExcelFile(path_gestionale)
            data = {
                'contatti': pd.read_excel(xls, sheet_name='Contatti'),
                'turni': pd.read_excel(xls, sheet_name='TurniDisponibili'),
                'prenotazioni': pd.read_excel(xls, sheet_name='Prenotazioni'),
                'sostituzioni': pd.read_excel(xls, sheet_name='SostituzioniPendenti')
            }

            if 'Tipo' not in data['turni'].columns:
                data['turni']['Tipo'] = 'Assistenza'
            data['turni']['Tipo'].fillna('Assistenza', inplace=True)

            required_notification_cols = ['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione']
            if 'Notifiche' in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name='Notifiche')
                df.columns = df.columns.str.strip()
                for col in required_notification_cols:
                    if col not in df.columns:
                        df[col] = pd.NA
                data['notifiche'] = df
            else:
                data['notifiche'] = pd.DataFrame(columns=required_notification_cols)

            required_bacheca_cols = ['ID_Bacheca', 'ID_Turno', 'Tecnico_Originale', 'Ruolo_Originale', 'Timestamp_Pubblicazione', 'Stato', 'Tecnico_Subentrante', 'Timestamp_Assegnazione']
            if 'TurniInBacheca' in xls.sheet_names:
                df_bacheca = pd.read_excel(xls, sheet_name='TurniInBacheca')
                df_bacheca.columns = df_bacheca.columns.str.strip()
                for col in required_bacheca_cols:
                    if col not in df_bacheca.columns:
                        df_bacheca[col] = pd.NA
                data['bacheca'] = df_bacheca
            else:
                data['bacheca'] = pd.DataFrame(columns=required_bacheca_cols)

            return data
        except Exception as e:
            st.error(f"Errore critico nel caricamento del file Gestionale: {e}")
            return None

def _save_to_excel_backend(data):
    with config.EXCEL_LOCK:
        try:
            path_gestionale = st.secrets["paths"]["PATH_GESTIONALE"]
            with pd.ExcelWriter(path_gestionale, engine='openpyxl') as writer:
                data['contatti'].to_excel(writer, sheet_name='Contatti', index=False)
                data['turni'].to_excel(writer, sheet_name='TurniDisponibili', index=False)
                data['prenotazioni'].to_excel(writer, sheet_name='Prenotazioni', index=False)
                data['sostituzioni'].to_excel(writer, sheet_name='SostituzioniPendenti', index=False)
                if 'notifiche' in data:
                    data['notifiche'].to_excel(writer, sheet_name='Notifiche', index=False)
                if 'bacheca' in data:
                    data['bacheca'].to_excel(writer, sheet_name='TurniInBacheca', index=False)
            return True
        except Exception as e:
            print(f"ERRORE CRITICO NEL THREAD DI SALVATAGGIO: {e}")
            return False

def salva_gestionale_async(data):
    st.cache_data.clear()
    data_copy = {k: v.copy() for k, v in data.items()}
    thread = threading.Thread(target=_save_to_excel_backend, args=(data_copy,))
    thread.start()
    return True

def carica_archivio_completo():
    try:
        path_storico = st.secrets["paths"]["STORICO_DB_PATH"]
        df = pd.read_excel(path_storico)
        df['Data_Riferimento_dt'] = pd.to_datetime(df['Data_Riferimento'], errors='coerce')
        df.dropna(subset=['Data_Riferimento_dt'], inplace=True)
        df.sort_values(by='Data_Compilazione', ascending=True, inplace=True)
        df.drop_duplicates(subset=['PdL', 'Tecnico', 'Data_Riferimento'], keep='last', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    try:
        nome_foglio = st.secrets["google_sheets"]["NOME_FOGLIO_RISPOSTE"]
        foglio_risposte = client.open(nome_foglio).sheet1
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
        <html><body><h2>Riepilogo Report Attività</h2>
        <p>Un report è stato <strong>{azione}</strong> dal tecnico {nome_completo}.</p>
        </body></html>
        """
        invia_email_con_outlook_async(titolo_email, html_body)
        return row_index
    except Exception as e:
        st.error(f"Errore salvataggio GSheets: {e}")
        return None

def trova_attivita(utente_completo, giorno, mese, anno, df_contatti):
    try:
        path_base = st.secrets["paths"]["PATH_GIORNALIERA_BASE"]
        path_giornaliera_mensile = os.path.join(path_base, f"Giornaliera {mese:02d}-{anno}.xlsm")
        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=str(giorno), engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45]

        pdls_utente = set()
        for _, riga in df_range.iterrows():
            nome_in_giornaliera = str(riga[5]).strip().lower()
            if utente_completo.lower() in nome_in_giornaliera:
                pdl_text = str(riga[9])
                if not pd.isna(pdl_text):
                    pdls_found = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
                    pdls_utente.update(pdls_found)
        if not pdls_utente:
            return []

        attivita_collezionate = {}
        df_storico_db = carica_archivio_completo()

        for _, riga in df_range.iterrows():
            pdl_text = str(riga[9])
            if pd.isna(pdl_text): continue
            lista_pdl_riga = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
            if not any(pdl in pdls_utente for pdl in lista_pdl_riga): continue

            desc_text = str(riga[6])
            nome_membro = str(riga[5]).strip()
            orario = f"{riga[10]}-{riga[11]}"
            if pd.isna(desc_text) or not nome_membro or nome_membro.lower() == 'nan': continue

            lista_descrizioni_riga = [line.strip() for line in desc_text.splitlines() if line.strip()]

            for pdl, desc in zip(lista_pdl_riga, lista_descrizioni_riga):
                if pdl not in pdls_utente: continue
                activity_key = (pdl, desc)
                if activity_key not in attivita_collezionate:
                    storico = []
                    if not df_storico_db.empty:
                        storico_df_pdl = df_storico_db[df_storico_db['PdL'] == pdl].copy()
                        if not storico_df_pdl.empty:
                            storico_df_pdl['Data_Riferimento'] = pd.to_datetime(storico_df_pdl['Data_Riferimento_dt']).dt.strftime('%d/%m/%Y')
                            storico = storico_df_pdl.to_dict('records')
                    attivita_collezionate[activity_key] = {'pdl': pdl, 'attivita': desc, 'storico': storico, 'team_members': {}}

                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    if df_contatti is not None and not df_contatti.empty:
                        matching_user = df_contatti[df_contatti['Nome Cognome'].str.strip().str.lower() == nome_membro.lower()]
                        if not matching_user.empty:
                            ruolo_membro = matching_user.iloc[0].get('Ruolo', 'Tecnico')
                    attivita_collezionate[activity_key]['team_members'][nome_membro] = {'ruolo': ruolo_membro, 'orari': set()}
                attivita_collezionate[activity_key]['team_members'][nome_membro]['orari'].add(orario)

        lista_attivita_finale = []
        for activity_data in attivita_collezionate.values():
            team_list = [{'nome': nome, 'ruolo': details['ruolo'], 'orari': sorted(list(details['orari']))} for nome, details in activity_data['team_members'].items()]
            activity_data['team'] = team_list
            del activity_data['team_members']
            lista_attivita_finale.append(activity_data)
        return lista_attivita_finale
    except FileNotFoundError:
        return []
    except Exception as e:
        st.error(f"Errore lettura giornaliera: {e}")
        return []

@st.cache_data(ttl=600)
def carica_dati_attivita_programmate():
    try:
        excel_path = st.secrets["paths"]["ATTIVITA_PROGRAMMATE_PATH"]
        storico_path = st.secrets["paths"]["STORICO_DB_PATH"]
    except KeyError:
        st.error("I percorsi ('paths') per i file di attività e storico non sono configurati correttamente in secrets.toml.")
        return pd.DataFrame()

    if not os.path.exists(excel_path):
        st.error(f"File attività programmate non trovato: {excel_path}")
        return pd.DataFrame()

    sheets_to_read = {
        'A1': {'tcl': 'Francesco Naselli', 'area': 'Area 1'},
        'A2': {'tcl': 'Francesco Naselli', 'area': 'Area 2'},
        'A3': {'tcl': 'Ferdinando Caldarella', 'area': 'Area 3'},
        'CTE': {'tcl': 'Ferdinando Caldarella', 'area': 'CTE'},
        'BLENDING': {'tcl': 'Ivan Messina', 'area': 'BLENDING'},
    }

    all_data = []
    giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

    try:
        df_storico_full = pd.read_excel(storico_path, sheet_name='DB')
        df_storico_full['PdL'] = df_storico_full['PdL'].astype(str)
        df_storico_full['Data_Riferimento_dt'] = pd.to_datetime(df_storico_full['Data_Riferimento'], errors='coerce')
        latest_status = df_storico_full.sort_values('Data_Compilazione').drop_duplicates('PdL', keep='last').set_index('PdL')['Stato'].to_dict()
    except FileNotFoundError:
        df_storico_full = pd.DataFrame(columns=['PdL', 'Stato', 'Data_Compilazione', 'Data_Riferimento_dt'])
        latest_status = {}
    except Exception:
        df_storico_full = pd.DataFrame(columns=['PdL', 'Stato', 'Data_Compilazione', 'Data_Riferimento_dt'])
        latest_status = {}

    status_map = {'DA EMETTERE': 'Pianificato', 'EMESSO': 'In Corso', 'DA CHIUDERE': 'Terminata', 'CHIUSO': 'Completato', 'ANNULLATO': 'Annullato'}

    for sheet_name, metadata in sheets_to_read.items():
        try:
            wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
            if sheet_name not in wb.sheetnames: continue
            ws = wb[sheet_name]
            data = list(ws.values)
            if len(data) < 2: continue

            header = [str(h) for h in data[0]]
            df = pd.DataFrame(data[1:], columns=header)

            required_cols = ['PdL', 'Impianto', 'DESCRIZIONE ESTESA', 'Stato OdL', 'Lun', 'Mar', 'Mer', 'Gio', 'Ven']
            if not all(col in df.columns for col in required_cols): continue

            df = df.dropna(subset=['PdL'])
            if df.empty: continue

            df_filtered = df[required_cols].copy()
            df_filtered.columns = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì']
            df_filtered['PdL'] = df_filtered['PdL'].astype(str)
            df_filtered['TCL'] = metadata['tcl']
            df_filtered['Area'] = metadata['area']

            giorni_programmati = df_filtered[giorni_settimana].apply(
                lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']),
                axis=1
            )
            df_filtered['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')

            def get_status(row):
                pdl_str = str(row['PdL']).strip()
                if pdl_str in latest_status: return latest_status[pdl_str]
                if pd.notna(row['Stato_OdL']): return status_map.get(str(row['Stato_OdL']).strip().upper(), 'Non Definito')
                return 'Pianificato'

            df_filtered['Stato'] = df_filtered.apply(get_status, axis=1)
            df_filtered['Storico'] = df_filtered['PdL'].apply(lambda p: df_storico_full[df_storico_full['PdL'] == p].sort_values(by='Data_Riferimento_dt', ascending=False).to_dict('records') if p in df_storico_full['PdL'].values else [])
            all_data.append(df_filtered)
        except Exception:
            pass

    if not all_data: return pd.DataFrame()
    final_df = pd.concat(all_data, ignore_index=True)
    return final_df
