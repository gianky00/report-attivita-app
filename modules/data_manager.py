import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading

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

#@st.cache_data
def carica_gestionale():
    with config.EXCEL_LOCK:
        try:
            xls = pd.ExcelFile(config.PATH_GESTIONALE)
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

            # Aggiunto per la bacheca turni
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
            st.error(f"Errore critico nel caricamento del file Gestionale_Tecnici.xlsx: {e}")
            return None

def _save_to_excel_backend(data):
    """Questa funzione è sicura per essere eseguita in un thread separato."""
    with config.EXCEL_LOCK:
        try:
            with pd.ExcelWriter(config.PATH_GESTIONALE, engine='openpyxl') as writer:
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
    """Funzione da chiamare dall'app Streamlit per un salvataggio non bloccante."""
    st.cache_data.clear()
    data_copy = {k: v.copy() for k, v in data.items()}
    thread = threading.Thread(target=_save_to_excel_backend, args=(data_copy,))
    thread.start()
    return True # Ritorna immediatamente

def carica_archivio_completo():
    try:
        df = pd.read_excel(config.PATH_STORICO_DB)
        df['Data_Riferimento_dt'] = pd.to_datetime(df['Data_Riferimento'], errors='coerce')
        df.dropna(subset=['Data_Riferimento_dt'], inplace=True)
        df.sort_values(by='Data_Compilazione', ascending=True, inplace=True)
        df.drop_duplicates(subset=['PdL', 'Tecnico', 'Data_Riferimento'], keep='last', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    try:
        foglio_risposte = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
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
        invia_email_con_outlook_async(titolo_email, html_body)
        return row_index
    except Exception as e:
        st.error(f"Errore salvataggio GSheets: {e}")
        return None

def trova_attivita(utente_completo, giorno, mese, anno, df_contatti):
    try:
        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")
        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=str(giorno), engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45]

        # 1. Trova tutti i PdL per l'utente corrente
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

        # 2. Raccogli tutte le attività e i membri del team per i PdL rilevanti
        attivita_collezionate = {} # Dizionario per raggruppare per (pdl, desc)
        df_storico_db = carica_archivio_completo()

        for _, riga in df_range.iterrows():
            pdl_text = str(riga[9])
            if pd.isna(pdl_text): continue

            lista_pdl_riga = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)

            # Controlla se c'è almeno un PdL rilevante in questa riga
            if not any(pdl in pdls_utente for pdl in lista_pdl_riga):
                continue

            desc_text = str(riga[6])
            nome_membro = str(riga[5]).strip()
            start_time = str(riga[10])
            end_time = str(riga[11])
            orario = f"{start_time}-{end_time}"

            if pd.isna(desc_text) or not nome_membro or nome_membro.lower() == 'nan':
                continue

            lista_descrizioni_riga = [line.strip() for line in desc_text.splitlines() if line.strip()]

            for pdl, desc in zip(lista_pdl_riga, lista_descrizioni_riga):
                if pdl not in pdls_utente: continue

                activity_key = (pdl, desc)
                if activity_key not in attivita_collezionate:
                    # Carica storico solo la prima volta che incontriamo l'attività
                    storico = []
                    if not df_storico_db.empty:
                        storico_df_pdl = df_storico_db[df_storico_db['PdL'] == pdl].copy()
                        if not storico_df_pdl.empty:
                            storico_df_pdl['Data_Riferimento'] = pd.to_datetime(storico_df_pdl['Data_Riferimento_dt']).dt.strftime('%d/%m/%Y')
                            storico = storico_df_pdl.to_dict('records')

                    attivita_collezionate[activity_key] = {
                        'pdl': pdl,
                        'attivita': desc,
                        'storico': storico,
                        'team_members': {} # Usiamo un dizionario per raggruppare gli orari per membro
                    }

                # Aggiungi o aggiorna il membro del team con il suo orario
                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    if df_contatti is not None and not df_contatti.empty:
                        matching_user = df_contatti[df_contatti['Nome Cognome'].str.strip().str.lower() == nome_membro.lower()]
                        if not matching_user.empty:
                            ruolo_membro = matching_user.iloc[0].get('Ruolo', 'Tecnico')

                    attivita_collezionate[activity_key]['team_members'][nome_membro] = {
                        'ruolo': ruolo_membro,
                        'orari': set()
                    }

                attivita_collezionate[activity_key]['team_members'][nome_membro]['orari'].add(orario)

        # 3. Formatta l'output finale
        lista_attivita_finale = []
        for activity_data in attivita_collezionate.values():
            team_list = []
            for nome, details in activity_data['team_members'].items():
                team_list.append({
                    'nome': nome,
                    'ruolo': details['ruolo'],
                    'orari': sorted(list(details['orari']))
                })

            activity_data['team'] = team_list
            del activity_data['team_members'] # Pulisci la struttura intermedia
            lista_attivita_finale.append(activity_data)

        return lista_attivita_finale
    except FileNotFoundError:
        return []
    except Exception as e:
        st.error(f"Errore lettura giornaliera: {e}")
        return []

@st.cache_data(ttl=300) # Cache per 5 minuti per migliorare performance
def carica_dati_attivita_programmate():
    """
    Carica i dati dal file Excel delle attività programmate, li unisce con lo
    stato reale dall'archivio storico e restituisce un DataFrame unificato.
    La gerarchia degli stati è:
    1. Stato dall'archivio web (se esiste)
    2. Stato mappato dalla colonna M dell'Excel
    3. 'Pianificato' come default
    """
    file_path = r"\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\ATTIVITA_PROGRAMMATE.xlsm"
    sheets_to_process = ["A1", "A2", "A3", "CTE", "BLENDING"]

    # --- Mappature e configurazioni ---
    PDL_COL_INDEX = 4       # Colonna E
    IMPIANTO_COL_INDEX = 5  # Colonna F
    STATO_EXCEL_COL_INDEX = 12 # Colonna M
    GIORNI_COL_INDICES = {"Lunedì": 7, "Martedì": 8, "Mercoledì": 9, "Giovedì": 10, "Venerdì": 11}

    tcl_map = {"A1": "Francesco Naselli", "A2": "Francesco Naselli", "A3": "Ferdinando Caldarella", "CTE": "Ferdinando Caldarella", "BLENDING": "Ivan Messina"}
    area_map = {"A1": "Area 1", "A2": "Area 2", "A3": "Area 3", "CTE": "CTE", "BLENDING": "BLENDING"}

    status_map_excel = {
        'DA CHIUDERE': 'TERMINATA',
        'EMESSO': 'IN CORSO',
        'IN CORSO': 'IN CORSO',
        'INTERROTTO': 'SOSPESA',
        'RICHIESTO': 'DA PROCESSARE'
    }

    # 1. Carica le attività pianificate da Excel
    planned_activities = []
    try:
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        for sheet_name in xls.sheet_names:
            if sheet_name in sheets_to_process:
                df_sheet = pd.read_excel(xls, sheet_name=sheet_name, header=None, skiprows=3)
                for _, row in df_sheet.iterrows():
                    pdl = row.iloc[PDL_COL_INDEX]
                    if pd.notna(pdl) and str(pdl).strip():
                        impianto = row.iloc[IMPIANTO_COL_INDEX]
                        giorni = [giorno for giorno, index in GIORNI_COL_INDICES.items() if index < len(row) and str(row.iloc[index]).strip().upper() == 'X']

                        stato_excel_raw = row.iloc[STATO_EXCEL_COL_INDEX] if STATO_EXCEL_COL_INDEX < len(row) else None
                        stato_iniziale = status_map_excel.get(str(stato_excel_raw).strip().upper(), 'Pianificato')

                        planned_activities.append({
                            'PdL': str(pdl).strip(),
                            'Impianto': impianto,
                            'StatoIniziale': stato_iniziale,
                            'GiorniProgrammati': ", ".join(giorni) if giorni else "Non Programmato",
                            'TCL': tcl_map.get(sheet_name, 'Non Definito'),
                            'Area': area_map.get(sheet_name, 'Non Definito'),
                            'Foglio': sheet_name
                        })
    except FileNotFoundError:
        st.error(f"File delle attività programmate non trovato: {file_path}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore durante la lettura del file Excel delle attività: {e}")
        return pd.DataFrame()

    if not planned_activities:
        return pd.DataFrame()

    df_planned = pd.DataFrame(planned_activities)
    df_planned.drop_duplicates(subset='PdL', keep='first', inplace=True)

    # 2. Carica l'archivio degli stati reali delle attività
    df_archived = carica_archivio_completo()
    if df_archived.empty:
        df_planned.rename(columns={'StatoIniziale': 'Stato'}, inplace=True)
        return df_planned

    df_archived['PdL'] = df_archived['PdL'].astype(str).str.strip()
    df_latest_status = df_archived.sort_values('Data_Riferimento_dt', ascending=True).drop_duplicates(subset='PdL', keep='last')

    # 3. Unisci le due fonti di dati
    df_merged = pd.merge(
        df_planned,
        df_latest_status[['PdL', 'Stato']],
        on='PdL',
        how='left'
    )

    # 4. Applica la gerarchia degli stati
    # Se lo 'Stato' dall'archivio è NaN, usa lo 'StatoIniziale' da Excel.
    df_merged['Stato'].fillna(df_merged['StatoIniziale'], inplace=True)
    df_merged.drop(columns=['StatoIniziale'], inplace=True)

    return df_merged
