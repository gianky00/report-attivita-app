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
from config import get_attivita_programmate_path, get_storico_db_path, get_gestionale_path, get_transito_db_path

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

            # Aggiunto per le richieste di materiali
            required_materiali_cols = ['ID_Richiesta', 'Richiedente', 'Timestamp', 'Stato', 'Dettagli']
            if 'RichiesteMateriali' in xls.sheet_names:
                df_materiali = pd.read_excel(xls, sheet_name='RichiesteMateriali')
                df_materiali.columns = df_materiali.columns.str.strip()
                for col in required_materiali_cols:
                    if col not in df_materiali.columns:
                        df_materiali[col] = pd.NA
                data['richieste_materiali'] = df_materiali
            else:
                data['richieste_materiali'] = pd.DataFrame(columns=required_materiali_cols)

            # Aggiunto per le richieste di assenze
            required_assenze_cols = ['ID_Richiesta', 'Richiedente', 'Timestamp', 'Tipo_Assenza', 'Data_Inizio', 'Data_Fine', 'Note', 'Stato']
            if 'RichiesteAssenze' in xls.sheet_names:
                df_assenze = pd.read_excel(xls, sheet_name='RichiesteAssenze')
                df_assenze.columns = df_assenze.columns.str.strip()
                for col in required_assenze_cols:
                    if col not in df_assenze.columns:
                        df_assenze[col] = pd.NA
                data['richieste_assenze'] = df_assenze
            else:
                data['richieste_assenze'] = pd.DataFrame(columns=required_assenze_cols)


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
            if 'richieste_materiali' in data:
                data['richieste_materiali'].to_excel(writer, sheet_name='RichiesteMateriali', index=False)
            if 'richieste_assenze' in data:
                data['richieste_assenze'].to_excel(writer, sheet_name='RichiesteAssenze', index=False)
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
    """
    Nuova versione della funzione che funge da wrapper per `carica_dati_attivita_programmate`.
    In futuro, questa funzione potrebbe essere rimossa e le chiamate potrebbero essere
    dirette a `carica_dati_attivita_programmate`, ma per ora manteniamo la compatibilità.
    """
    return carica_dati_attivita_programmate()

def _append_to_transit_db(data_row):
    """
    Funzione di supporto per aggiungere una riga di dati al file di transito .xlsm,
    preservando le macro.
    """
    transit_db_path = config.get_transito_db_path()
    try:
        SHEET_NAME = "transit_reports"
        # Carica il workbook esistente o ne crea uno nuovo se non esiste
        if os.path.exists(transit_db_path):
            workbook = openpyxl.load_workbook(transit_db_path, keep_vba=True)
            if SHEET_NAME in workbook.sheetnames:
                sheet = workbook[SHEET_NAME]
            else:
                sheet = workbook.create_sheet(SHEET_NAME)
                # Aggiungi l'header se il foglio è nuovo
                header = ["Timestamp", "Tecnico", "Descrizione_Attivita", "Report", "Stato", "Data_Riferimento"]
                sheet.append(header)
        else:
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = SHEET_NAME
            header = ["Timestamp", "Tecnico", "Descrizione_Attivita", "Report", "Stato", "Data_Riferimento"]
            sheet.append(header)

        sheet.append(data_row)
        workbook.save(transit_db_path)
        return True
    except Exception as e:
        # Logga l'errore ma non bloccare l'applicazione principale
        print(f"ERRORE: Impossibile scrivere sul file di transito '{transit_db_path}': {e}")
        return False


def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    """
    Scrive il report su Google Sheets (primario) e su un file di transito locale (secondario).
    """
    try:
        foglio_risposte = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data_riferimento_str = data_riferimento.strftime('%d/%m/%Y')

        # Dati formattati per entrambi i sistemi
        dati_formattati = [
            timestamp,
            nome_completo,
            dati_da_scrivere['descrizione'],
            dati_da_scrivere['report'],
            dati_da_scrivere['stato'],
            data_riferimento_str
        ]

        # 1. Scrittura su Google Sheets (azione primaria)
        if row_index:
            foglio_risposte.update(f'A{row_index}:F{row_index}', [dati_formattati])
            azione = "aggiornato"
        else:
            foglio_risposte.append_row(dati_formattati)
            row_index = len(foglio_risposte.get_all_values())
            azione = "inviato"

        # 2. Scrittura sul file di transito locale (azione secondaria)
        # Questa operazione avviene indipendentemente dall'aggiornamento o inserimento
        _append_to_transit_db(dati_formattati)

        # 3. Invio notifica email (come prima)
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
                <td>{data_riferimento_str}</td>
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
        st.error(f"Errore durante la scrittura su Google Sheets: {e}")
        # Anche se GSheets fallisce, prova a scrivere sul file di transito come fallback
        timestamp_fallback = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data_riferimento_fallback_str = data_riferimento.strftime('%d/%m/%Y')
        dati_fallback = [
            timestamp_fallback, nome_completo, dati_da_scrivere['descrizione'],
            dati_da_scrivere['report'], dati_da_scrivere['stato'], data_riferimento_fallback_str
        ]
        if _append_to_transit_db(dati_fallback):
            st.warning("La scrittura su Google Sheets è fallita, ma il report è stato salvato localmente nel file di transito.")
        else:
            st.error("FALLIMENTO CRITICO: Impossibile salvare il report sia su Google Sheets che sul file di transito locale.")
        return None

def _match_partial_name(partial_name, full_name):
    """
    Intelligently matches a partial name (e.g., 'Garro L.') with a full name (e.g., 'Luca Garro').
    """
    if not partial_name or not full_name:
        return False

    # Normalize and split names into parts
    partial_parts = [p.replace('.', '') for p in partial_name.lower().split()]
    full_parts = full_name.lower().split()

    # Separate names and initials from the partial name
    partial_initials = {p for p in partial_parts if len(p) == 1}
    partial_names = {p for p in partial_parts if len(p) > 1}

    # All name parts from the partial name must be in the full name
    if not partial_names.issubset(set(full_parts)):
        return False

    # Get the parts of the full name that are not in the partial name (potential first names)
    remaining_full_parts = set(full_parts) - partial_names

    # Get the initials of the remaining parts
    remaining_initials = {p[0] for p in remaining_full_parts}

    # All initials from the partial name must match the initials of the remaining parts
    if not partial_initials.issubset(remaining_initials):
        return False

    return True

def trova_attivita(utente_completo, giorno, mese, anno, df_contatti):
    try:
        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")

        target_sheet = str(giorno)
        try:
            workbook = openpyxl.load_workbook(path_giornaliera_mensile, read_only=True)
            day_str = str(giorno)
            for sheet_name in workbook.sheetnames:
                if day_str in sheet_name.split():
                    target_sheet = sheet_name
                    break
        except Exception:
            pass

        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=target_sheet, engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45]

        pdls_utente = set()
        for _, riga in df_range.iterrows():
            if 5 < len(riga) and 9 < len(riga):
                nome_in_giornaliera = str(riga[5]).strip().lower()
                if nome_in_giornaliera and nome_in_giornaliera in utente_completo.lower():
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
                        'team_members': {}
                    }
                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    if df_contatti is not None and not df_contatti.empty:
                        for _, contact_row in df_contatti.iterrows():
                            full_name = contact_row['Nome Cognome']
                            if _match_partial_name(nome_membro, full_name):
                                ruolo_membro = contact_row.get('Ruolo', 'Tecnico')
                                break
                    attivita_collezionate[activity_key]['team_members'][nome_membro] = {
                        'ruolo': ruolo_membro,
                        'orari': set()
                    }
                attivita_collezionate[activity_key]['team_members'][nome_membro]['orari'].add(orario)

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
            del activity_data['team_members']
            lista_attivita_finale.append(activity_data)
        return lista_attivita_finale
    except FileNotFoundError:
        return []
    except Exception as e:
        st.error(f"Errore lettura giornaliera: {e}")
        return []

@st.cache_data(ttl=300) # Ridotto il TTL per riflettere dati più dinamici
def carica_dati_attivita_programmate():
    """
    Carica e processa i dati direttamente dal database principale ATTIVITA_PROGRAMMATE.xlsx,
    che ora è la fonte di verità per lo stato delle attività.
    """
    excel_path = config.get_attivita_programmate_path()

    if not os.path.exists(excel_path):
        st.error(f"Database principale non trovato: {excel_path}")
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

    status_map = {
        'DA EMETTERE': 'Pianificato', 'CHIUSO': 'Completato', 'ANNULLATO': 'Annullato',
        'INTERROTTO': 'Sospeso', 'RICHIESTO': 'Da processare', 'EMESSO': 'Processato',
        'IN CORSO': 'Aperto', 'DA CHIUDERE': 'Terminata'
    }

    for sheet_name, metadata in sheets_to_read.items():
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            df.columns = [str(col).strip() for col in df.columns]

            required_cols = ['PdL', 'IMP.', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'LUN', 'MAR', 'MER', 'GIO', 'VEN']
            if not all(col in df.columns for col in required_cols):
                continue

            df.dropna(subset=['PdL'], inplace=True)
            if df.empty:
                continue

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
            
            # Lo stato viene ora letto direttamente dalla colonna 'STATO PdL' e mappato
            df_filtered['Stato'] = df_filtered['Stato_OdL'].map(status_map).fillna('Non Definito')

            # La colonna 'Storico' non è più necessaria qui, poiché questo è il DB principale
            df_filtered['Storico'] = [[] for _ in range(len(df_filtered))]

            all_data.append(df_filtered)
        except Exception as e:
            st.warning(f"Errore durante l'elaborazione del foglio '{sheet_name}': {e}")
            continue

    if not all_data:
        st.warning("Nessun dato valido trovato nel database principale.")
        return pd.DataFrame()

    final_df = pd.concat(all_data, ignore_index=True)
    return final_df

# --- NUOVA LOGICA DI SINCRONIZZAZIONE MANUALE ---

def _leggi_report_da_google(client):
    """Legge i dati grezzi dei report dal foglio Google specificato."""
    try:
        sheet = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"Errore durante la lettura dei dati da Google Sheets: {e}")
        return None

def _processa_dati_grezzi(df_grezzo):
    """Processa i dati grezzi letti da Google per prepararli all'inserimento nel database."""
    if df_grezzo is None:
        return None

    lista_attivita_pulite = []

    # Nomi delle colonne come appaiono nel foglio Google
    COLONNA_TIMESTAMP = 'Informazioni cronologiche'
    COLONNA_UTENTE = 'Nome e Cognome'
    COLONNA_DESCRIZIONE_PDL = '1. Descrizione PdL'
    COLONNA_REPORT = '1. Report Attività'
    COLONNA_STATO = '1. Stato attività'
    COLONNA_DATA_RIFERIMENTO = 'Data Riferimento Attività'

    # Validazione colonne
    colonne_necessarie = [COLONNA_TIMESTAMP, COLONNA_UTENTE, COLONNA_DESCRIZIONE_PDL, COLONNA_REPORT, COLONNA_STATO]
    for col in colonne_necessarie:
        if col not in df_grezzo.columns:
            st.error(f"Errore critico: La colonna '{col}' non è stata trovata nel foglio Google!")
            return None

    for _, riga in df_grezzo.iterrows():
        if pd.isna(riga[COLONNA_DESCRIZIONE_PDL]) or str(riga[COLONNA_DESCRIZIONE_PDL]).strip() == '':
            continue

        descrizione_completa = str(riga[COLONNA_DESCRIZIONE_PDL])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        pdl = pdl_match.group(1) if pdl_match else ''
        descrizione_pulita = re.sub(r'PdL \d{6}/?[CS]?\s*[-:]?\s*', '', descrizione_completa).strip()

        data_riferimento_str = str(riga.get(COLONNA_DATA_RIFERIMENTO, '')).strip()
        if data_riferimento_str:
            data_riferimento = data_riferimento_str
        else:
            timestamp_str = str(riga.get(COLONNA_TIMESTAMP, ''))
            match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})', timestamp_str)
            data_riferimento = match.group(1).replace('-', '/').replace('.', '/') if match else datetime.date.today().strftime('%d/%m/%Y')

        nuova_riga = {
            'PdL': pdl,
            'Descrizione': descrizione_pulita,
            'Stato': riga[COLONNA_STATO],
            'Tecnico': riga[COLONNA_UTENTE],
            'Report': riga[COLONNA_REPORT],
            'Data_Compilazione': riga[COLONNA_TIMESTAMP],
            'Data_Riferimento': data_riferimento
        }
        lista_attivita_pulite.append(nuova_riga)

    if not lista_attivita_pulite:
        return None

    return pd.DataFrame(lista_attivita_pulite)

def _salva_excel_preservando_macro(df, file_path, sheet_name, table_name=None):
    """
    Funzione generica per salvare un DataFrame in un file Excel (.xlsm),
    preservando le macro (VBA).
    - Cancella i dati esistenti nel foglio (escluso l'header).
    - Scrive i nuovi dati dal DataFrame.
    - Opzionalmente, formatta i dati come una tabella di Excel.
    """
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter

    try:
        # Se il file non esiste, lo crea da zero
        if not os.path.exists(file_path):
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name
            # Scrive l'header per il nuovo file
            ws.append(df.columns.tolist())
        else:
            wb = load_workbook(file_path, keep_vba=True)
            if sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                # Cancella i vecchi dati ma non l'header
                if ws.max_row > 1:
                    ws.delete_rows(2, ws.max_row - 1)
            else:
                # Se il foglio non esiste, lo crea
                ws = wb.create_sheet(title=sheet_name)
                ws.append(df.columns.tolist())

        # Scrive i dati dal DataFrame nel foglio
        for r in dataframe_to_rows(df, index=False, header=False):
            ws.append(r)

        # Gestione della tabella (se richiesto)
        if table_name:
            # Rimuove la tabella esistente se presente
            if table_name in ws.tables:
                del ws.tables[table_name]

            # Crea la nuova tabella solo se ci sono dati
            if not df.empty:
                max_row, max_col = len(df) + 1, len(df.columns)
                table_range = f"A1:{get_column_letter(max_col)}{max_row}"
                tab = Table(displayName=table_name, ref=table_range)
                style = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                tab.tableStyleInfo = style
                ws.add_table(tab)

        wb.save(file_path)
        return True, f"File '{os.path.basename(file_path)}' salvato con successo."
    except Exception as e:
        return False, f"Errore durante il salvataggio del file Excel '{os.path.basename(file_path)}': {e}"

def sync_reports_from_google(client_google):
    """
    Funzione principale per orchestrare la sincronizzazione dei report.
    """
    # 1. Leggi i dati da Google Sheets
    df_grezzo = _leggi_report_da_google(client_google)
    if df_grezzo is None:
        return True, "Nessun nuovo report trovato su Google Sheets o foglio vuoto."

    # 2. Processa i dati
    df_nuovi_report = _processa_dati_grezzi(df_grezzo)
    if df_nuovi_report is None:
        return True, "I nuovi report erano vuoti o non validi dopo il processamento."

    # 3. Carica il database esistente
    percorso_db = get_storico_db_path()
    try:
        df_esistente = pd.read_excel(percorso_db)
    except FileNotFoundError:
        df_esistente = pd.DataFrame() # Il file non esiste, verrà creato
    except Exception as e:
        return False, f"Errore nel caricamento del database esistente: {e}"

    # 4. Aggiorna il database
    df_combinato = pd.concat([df_esistente, df_nuovi_report], ignore_index=True)
    colonne_identificative = ['Tecnico', 'Data_Riferimento', 'PdL']
    df_combinato.sort_values('Data_Compilazione', ascending=True, inplace=True)
    df_combinato.drop_duplicates(subset=colonne_identificative, keep='last', inplace=True)
    df_ordinato = df_combinato.sort_values(by=['Data_Riferimento', 'PdL', 'Tecnico'], ascending=[False, True, True])

    # 5. Salva il database aggiornato usando la nuova funzione generica
    success, message = _salva_excel_preservando_macro(
        df=df_ordinato,
        file_path=percorso_db,
        sheet_name='Database_Attivita',
        table_name='TabellaAttivita'
    )

    # 6. Pulisci la cache se il salvataggio è andato a buon fine
    if success:
        st.cache_data.clear()

    return success, message

def update_reports_in_excel_and_google(df_aggiornato, client_google):
    """
    Aggiorna i report sia nel file Excel locale che nel foglio Google.
    """
    # 1. Salva nel file Excel
    percorso_db = get_storico_db_path()
    success_excel, message_excel = _salva_excel_preservando_macro(
        df=df_aggiornato,
        file_path=percorso_db,
        sheet_name='Database_Attivita',
        table_name='TabellaAttivita'
    )

    if not success_excel:
        return False, f"Errore durante il salvataggio su Excel: {message_excel}"

    # 2. Salva su Google Sheets
    try:
        sheet = client_google.open(config.NOME_FOGLIO_RISPOSTE).sheet1

        # Prepara il DataFrame per il caricamento
        # Le colonne devono corrispondere a quelle del foglio Google
        df_per_google = df_aggiornato.rename(columns={
            'Data_Compilazione': 'Informazioni cronologiche',
            'Tecnico': 'Nome e Cognome',
            'Descrizione': '1. Descrizione PdL', # Questo richiede una ricostruzione
            'Report': '1. Report Attività',
            'Stato': '1. Stato attività',
            'Data_Riferimento': 'Data Riferimento Attività'
        })

        # Ricostruisci la colonna '1. Descrizione PdL'
        df_per_google['1. Descrizione PdL'] = 'PdL ' + df_per_google['PdL'].astype(str) + ' - ' + df_per_google['1. Descrizione PdL'].astype(str)

        # Seleziona e ordina le colonne per corrispondere al foglio Google
        colonne_google = [
            'Informazioni cronologiche', 'Nome e Cognome', '1. Descrizione PdL',
            '1. Report Attività', '1. Stato attività', 'Data Riferimento Attività'
        ]
        df_per_google = df_per_google[colonne_google]

        # Svuota il foglio e scrivi i nuovi dati
        sheet.clear()
        sheet.update([df_per_google.columns.values.tolist()] + df_per_google.values.tolist())

        message_google = "Foglio Google aggiornato con successo."

    except Exception as e:
        return False, f"Errore durante l'aggiornamento di Google Sheets: {e}"

    # 3. Pulisci la cache
    st.cache_data.clear()

    return True, f"{message_excel}\n{message_google}"

def consolida_report(client_google):
    """
    Orchestra il processo di consolidamento dei report dal file di transito al database principale.
    """
    path_transito = config.get_transito_db_path()
    path_principale = config.get_attivita_programmate_path()

    # 1. Leggi i report dal file di transito
    try:
        if not os.path.exists(path_transito):
            return "success", "Nessun report da consolidare (file di transito non trovato)."
        # Legge esplicitamente dal foglio corretto
        df_transito = pd.read_excel(path_transito, sheet_name="transit_reports")
        if df_transito.empty:
            return "success", "Nessun report da consolidare (file di transito vuoto)."
    except Exception as e:
        return "error", f"Errore durante la lettura del file di transito: {e}"

    # 2. Leggi e aggiorna il database principale
    try:
        # --- Logica di consolidamento ottimizzata ---
        workbook = openpyxl.load_workbook(path_principale, keep_vba=True)

        # 1. Crea una mappa PdL -> Foglio per una ricerca efficiente
        pdl_to_sheet_map = {}
        for sheet_name in workbook.sheetnames:
            if sheet_name in ['Legenda', 'Template']: continue # Salta fogli non di dati
            ws = workbook[sheet_name]
            # Assumiamo che il PdL sia in colonna 1 (A)
            for row in range(2, ws.max_row + 1):
                pdl = ws.cell(row=row, column=1).value
                if pdl:
                    pdl_to_sheet_map[str(pdl)] = sheet_name

        # 2. Processa i report e raggruppali per foglio
        updates_by_sheet = {}
        for _, report in df_transito.iterrows():
            pdl_match = re.search(r'PdL\s*(\d{6}/[CS]|\d{6})', str(report['Descrizione_Attivita']))
            if not pdl_match: continue

            pdl = pdl_match.group(1)
            if pdl in pdl_to_sheet_map:
                target_sheet = pdl_to_sheet_map[pdl]
                if target_sheet not in updates_by_sheet:
                    updates_by_sheet[target_sheet] = {}
                # Mappa PdL -> nuovo stato
                updates_by_sheet[target_sheet][pdl] = report['Stato']

        # 3. Applica gli aggiornamenti foglio per foglio
        report_processati = 0
        for sheet_name, updates in updates_by_sheet.items():
            ws = workbook[sheet_name]
            header = [cell.value for cell in ws[1]]
            try:
                pdl_col_idx = header.index('PdL') + 1
                stato_col_idx = header.index('STATO\nPdL') + 1
            except ValueError:
                continue

            for row in range(2, ws.max_row + 1):
                pdl_val = str(ws.cell(row=row, column=pdl_col_idx).value)
                if pdl_val in updates:
                    ws.cell(row=row, column=stato_col_idx).value = updates[pdl_val]
                    report_processati += 1

        workbook.save(path_principale)

        # 4. Svuota le fonti solo DOPO che il salvataggio è andato a buon fine
        try:
            # Svuota il file di transito
            df_vuoto = pd.DataFrame(columns=df_transito.columns)
            _salva_excel_preservando_macro(df_vuoto, path_transito, "transit_reports", None)

            # Svuota il foglio Google
            sheet_google = client_google.open(config.NOME_FOGLIO_RISPOSTE).sheet1
            sheet_google.clear()
            header_google = ["Informazioni cronologiche", "Nome e Cognome", "1. Descrizione PdL", "1. Report Attività", "1. Stato attività", "Data Riferimento Attività"]
            sheet_google.append_row(header_google)
        except Exception as e:
            # Se la pulizia fallisce, non è un errore bloccante, ma va segnalato
            return "warning", f"Consolidamento completato, ma errore durante la pulizia delle fonti: {e}"

        return "success", f"Consolidamento completato. {report_processati} report sono stati processati e le fonti sono state pulite."

    except Exception as e:
        return "error", f"Errore durante il consolidamento dei dati nel database principale: {e}"