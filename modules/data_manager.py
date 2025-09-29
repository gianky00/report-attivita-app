import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading
import openpyxl

import config
from config import get_attivita_programmate_path, get_storico_db_path, get_gestionale_path

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
    """
    Carica tutti i dati gestionali direttamente dal database SQLite.
    """
    import sqlite3
    DB_NAME = "schedario.db"

    if not os.path.exists(DB_NAME):
        st.error(f"Database '{DB_NAME}' non trovato. Eseguire lo script di avvio.")
        return None

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)

        tabelle = [
            "contatti", "turni", "prenotazioni", "sostituzioni",
            "notifiche", "bacheca", "richieste_materiali", "richieste_assenze", "access_logs"
        ]

        data = {}
        for tabella in tabelle:
            try:
                # Carica ogni tabella in un DataFrame
                data[tabella] = pd.read_sql_query(f"SELECT * FROM {tabella}", conn)
            except pd.io.sql.DatabaseError as e:
                # Se una tabella non esiste o è vuota, crea un DataFrame vuoto
                # Questo può accadere se lo schema è aggiornato ma il DB no
                print(f"Avviso: tabella '{tabella}' non trovata o vuota nel DB. Errore: {e}")
                # Per sicurezza, proviamo a leggere le colonne dallo schema
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({tabella});")
                columns = [info[1] for info in cursor.fetchall()]
                data[tabella] = pd.DataFrame(columns=columns)

        # Gestione retrocompatibilità per la colonna 'Tipo' (se necessario)
        if 'turni' in data and 'Tipo' not in data['turni'].columns:
            data['turni']['Tipo'] = 'Assistenza'
        if 'turni' in data:
             data['turni']['Tipo'] = data['turni']['Tipo'].fillna('Assistenza')

        return data

    except sqlite3.Error as e:
        st.error(f"Errore critico durante la lettura dal database gestionale: {e}")
        return None
    finally:
        if conn:
            conn.close()

def _save_to_db_backend(data):
    """
    Funzione di backend per salvare i dati nel database SQLite.
    Questa funzione viene eseguita in un thread separato.
    """
    import sqlite3
    DB_NAME = "schedario.db"
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        # Usiamo un lock per sicurezza, anche se SQLite gestisce le concorrenze a livello di file
        with config.EXCEL_LOCK:
            for table_name, df in data.items():
                if not isinstance(df, pd.DataFrame):
                    continue
                # Sovrascrive completamente la tabella con i nuovi dati
                df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"ERRORE CRITICO NEL THREAD DI SALVATAGGIO DB: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def salva_gestionale_async(data):
    """
    Salva i dati gestionali nel database SQLite in modo asincrono.
    """
    st.cache_data.clear() # Pulisce la cache per forzare il ricaricamento
    data_copy = {k: v.copy() for k, v in data.items() if isinstance(v, pd.DataFrame)}
    thread = threading.Thread(target=_save_to_db_backend, args=(data_copy,))
    thread.start()
    return True # Ritorna immediatamente



def carica_archivio_completo():
    """
    Nuova logica: Carica lo storico direttamente dal file ATTIVITA_PROGRAMMATE.xlsx,
    che ora è l'unica fonte di verità.
    La funzione simula un "archivio" per compatibilità con le funzioni esistenti.
    """
    excel_path = get_attivita_programmate_path()
    all_data = []

    sheets_to_read = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']
    # Correggo la colonna del report con quella giusta: 'STATO\nATTIVITA''
    cols_to_extract = ['PdL', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO', "STATO\nATTIVITA'"]

    for sheet_name in sheets_to_read:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            df.columns = [str(col).strip() for col in df.columns]

            # Assicurati che la colonna del report esista, altrimenti creala vuota
            if "STATO\nATTIVITA'" not in df.columns:
                df["STATO\nATTIVITA'"] = ""

            if all(col in df.columns for col in cols_to_extract):
                df_sheet = df[cols_to_extract].copy()
                all_data.append(df_sheet)
        except Exception:
            continue

    if not all_data:
        return pd.DataFrame()

    df_archivio = pd.concat(all_data, ignore_index=True)
    df_archivio.dropna(subset=['PdL', 'DATA\nCONTROLLO'], inplace=True)

    # Rinomina le colonne per corrispondere allo schema atteso
    df_archivio.rename(columns={
        "DESCRIZIONE\nATTIVITA'": "Descrizione",
        "STATO\nPdL": "Stato",
        "DATA\nCONTROLLO": "Data_Riferimento",
        "PERSONALE\nIMPIEGATO": "Tecnico",
        "STATO\nATTIVITA'": "Report" # Mappa la colonna corretta a Report
    }, inplace=True)

    # Riempi i report vuoti con un testo standard
    df_archivio['Report'].fillna("Nessun report disponibile.", inplace=True)

    # Aggiungi colonne mancanti per compatibilità
    df_archivio['Data_Compilazione'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')
    df_archivio['Data_Riferimento_dt'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')

    return df_archivio

def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    """
    Orchestra la scrittura di un report su tutte le destinazioni necessarie:
    1. Google Sheets (come "inbox" primaria).
    2. File di transito Excel (Database_Report_Attivita.xlsm) per la disponibilità immediata.
    3. Notifica via email.
    """
    row_index_gs = None
    azione = "sconosciuta"
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_riferimento_str = data_riferimento.strftime('%d/%m/%Y')

    # --- 1. SCRITTURA SU GOOGLE SHEETS ---
    try:
        foglio_risposte = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        dati_formattati_gs = [timestamp, nome_completo, dati_da_scrivere['descrizione'], dati_da_scrivere['report'], dati_da_scrivere['stato'], data_riferimento_str]

        if row_index:
            foglio_risposte.update(f'A{row_index}:F{row_index}', [dati_formattati_gs])
            row_index_gs = row_index
            azione = "aggiornato"
        else:
            foglio_risposte.append_row(dati_formattati_gs)
            row_index_gs = len(foglio_risposte.get_all_values())
            azione = "inviato"
    except Exception as e:
        st.error(f"Errore critico durante il salvataggio su Google Sheets: {e}")
        return None # Blocca l'operazione se la scrittura primaria fallisce

    # --- 2. SCRITTURA SU FILE DI TRANSITO EXCEL (UPSERT) ---
    try:
        # Estrai PdL e Descrizione dal testo combinato
        descrizione_completa = str(dati_da_scrivere['descrizione'])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        pdl = pdl_match.group(1) if pdl_match else ''
        descrizione_pulita = re.sub(r'PdL \d{6}/?[CS]?\s*[-:]?\s*', '', descrizione_completa).strip()

        # Prepara la riga per il DataFrame
        dati_per_excel = {
            'PdL': pdl,
            'Descrizione': descrizione_pulita,
            'Stato': dati_da_scrivere['stato'],
            'Tecnico': nome_completo,
            'Report': dati_da_scrivere['report'],
            'Data_Compilazione': timestamp,
            'Data_Riferimento': data_riferimento_str
        }
        df_nuovo_report = pd.DataFrame([dati_per_excel])

        percorso_db = get_storico_db_path()
        with config.EXCEL_LOCK:
            try:
                df_esistente = pd.read_excel(percorso_db, sheet_name='Database_Attivita')
            except (FileNotFoundError, ValueError): # Gestisce sia file non trovato che foglio vuoto
                df_esistente = pd.DataFrame()

            # Logica di "upsert": rimuovi la vecchia riga se esiste
            if not df_esistente.empty:
                # Normalizza le colonne per un confronto sicuro
                df_esistente['PdL'] = df_esistente['PdL'].astype(str)
                df_esistente['Tecnico'] = df_esistente['Tecnico'].astype(str)
                df_esistente['Data_Riferimento'] = pd.to_datetime(df_esistente['Data_Riferimento'], errors='coerce').dt.strftime('%d/%m/%Y')

                mask = (
                    (df_esistente['PdL'] == dati_per_excel['PdL']) &
                    (df_esistente['Tecnico'] == dati_per_excel['Tecnico']) &
                    (df_esistente['Data_Riferimento'] == dati_per_excel['Data_Riferimento'])
                )
                df_esistente = df_esistente[~mask]

            df_aggiornato = pd.concat([df_esistente, df_nuovo_report], ignore_index=True)

            success, message = _salva_db_excel(df_aggiornato, percorso_db)
            if not success:
                st.warning(f"Salvataggio su file di transito Excel fallito: {message}")

    except Exception as e:
        st.warning(f"Un errore non gestito è occorso durante la scrittura sul file di transito: {e}")

    # --- 3. INVIO EMAIL DI NOTIFICA ---
    from modules.email_sender import invia_email_con_outlook_async
    titolo_email = f"Report Attività {azione.upper()} da: {nome_completo}"
    report_html = dati_da_scrivere['report'].replace('\n', '<br>')
    html_body = f"""
    <html><head><style>
        body {{ font-family: Calibri, sans-serif; }} table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }} th {{ background-color: #f2f2f2; }}
        .report-content {{ white-space: pre-wrap; word-wrap: break-word; }}
    </style></head><body>
    <h2>Riepilogo Report Attività</h2>
    <p>Un report è stato <strong>{azione}</strong> dal tecnico {nome_completo}.</p>
    <table>
        <tr><th>Data di Riferimento Attività</th><td>{data_riferimento_str}</td></tr>
        <tr><th>Data e Ora Invio Report</th><td>{timestamp}</td></tr>
        <tr><th>Tecnico</th><td>{nome_completo}</td></tr>
        <tr><th>Attività</th><td>{dati_da_scrivere['descrizione']}</td></tr>
        <tr><th>Stato Finale</th><td><b>{dati_da_scrivere['stato']}</b></td></tr>
        <tr><th>Report Compilato</th><td class="report-content">{report_html}</td></tr>
    </table></body></html>
    """
    invia_email_con_outlook_async(titolo_email, html_body)

    return row_index_gs

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

@st.cache_data(ttl=600)
def carica_dati_attivita_programmate():
    """
    Carica i dati delle attività programmate direttamente dal database SQLite.
    Questa funzione è molto più veloce rispetto alla lettura del file Excel.
    """
    import sqlite3

    DB_NAME = "schedario.db"
    TABLE_NAME = "attivita_programmate"

    if not os.path.exists(DB_NAME):
        st.error(f"Database '{DB_NAME}' non trovato. Eseguire lo script di avvio per crearlo e sincronizzarlo.")
        return pd.DataFrame()

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        # Leggi tutti i dati dalla tabella e caricali in un DataFrame pandas
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)

        # La colonna 'Storico' è memorizzata come stringa JSON.
        # Dobbiamo riconvertirla in un oggetto Python (lista di dizionari).
        def parse_storico_json(json_string):
            try:
                # Se la stringa non è vuota o None, la parsifichiamo
                if json_string:
                    return json.loads(json_string)
                # Altrimenti, restituiamo una lista vuota, come si aspetta l'UI
                return []
            except (json.JSONDecodeError, TypeError):
                # In caso di errore (es. stringa non valida), restituisci una lista vuota
                return []

        if 'Storico' in df.columns:
            df['Storico'] = df['Storico'].apply(parse_storico_json)
        else:
            # Se la colonna non dovesse esistere, la creiamo vuota per sicurezza
            df['Storico'] = [[] for _ in range(len(df))]

        return df

    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore durante la lettura dal database: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

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

def _salva_db_excel(df, percorso_salvataggio):
    """Salva il DataFrame nel file Excel, preservando le macro."""
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.styles import Font
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter

    file_template = os.path.join(os.path.dirname(percorso_salvataggio), "Database_Template.xlsm")
    file_da_usare = percorso_salvataggio if os.path.exists(percorso_salvataggio) else file_template

    try:
        wb = load_workbook(file_da_usare, keep_vba=True)
        ws = wb['Database_Attivita']

        # Cancella tutti i dati esistenti sotto l'header per evitare "dati fantasma"
        # Itera da max_row a 2 in ordine inverso per evitare problemi con l'eliminazione
        if ws.max_row > 1:
            for row_idx in range(ws.max_row, 1, -1):
                # Elimina l'intera riga
                ws.delete_rows(row_idx)

        # Scrivi i nuovi dati direttamente nelle celle, a partire dalla riga 2
        if not df.empty:
            for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
                for c_idx, value in enumerate(row, 1):
                    ws.cell(row=r_idx, column=c_idx, value=value)

        # Rimuovi e ricrea la tabella per aggiornare il range in modo sicuro
        if 'TabellaAttivita' in ws.tables:
            del ws.tables['TabellaAttivita']

        if not df.empty:
            max_row, max_col = len(df) + 1, len(df.columns)
            table_range = f"A1:{get_column_letter(max_col)}{max_row}"
            tab = Table(displayName="TabellaAttivita", ref=table_range)
            style = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
            tab.tableStyleInfo = style
            ws.add_table(tab)

        wb.save(percorso_salvataggio)
        return True, f"Database salvato con successo in '{os.path.basename(percorso_salvataggio)}'."
    except FileNotFoundError:
        return False, f"Errore: File template '{os.path.basename(file_template)}' o database esistente non trovato."
    except Exception as e:
        return False, f"Errore durante il salvataggio del file Excel: {e}"

def consolida_report_giornalieri(client_google):
    """
    Funzione di consolidamento definitiva che usa l'automazione di Excel per preservare l'integrità del file.
    Applica la mappatura dei dati richiesta.
    """
    import win32com.client as win32
    import pythoncom

    path_transito = get_storico_db_path()
    path_principale = get_attivita_programmate_path()
    aggiornamenti_effettuati = 0

    # --- NUOVE COLONNE DI DESTINAZIONE E MAPPATURA ---
    colonna_stato_target = "STATO\nPdL"        # Colonna M
    colonna_report_target = "STATO\nATTIVITA'"  # Colonna R
    colonna_personale_target = "PERSONALE\nIMPIEGATO" # Colonna S

    status_mapping = {
        'TERMINATA': 'TERMINATA',
        'SOSPESA': 'INTERROTTO',
        'IN CORSO': 'EMESSO'
    }

    # 1. Legge i report dal file di transito
    try:
        with config.EXCEL_LOCK:
            df_transito = pd.read_excel(path_transito, sheet_name='Database_Attivita')
        if df_transito.empty:
            return True, "Nessun nuovo report da consolidare."
    except (FileNotFoundError, ValueError):
        return True, "File di transito non trovato o vuoto. Nessuna azione eseguita."
    except Exception as e:
        return False, f"Errore durante la lettura del file di transito: {e}"

    # --- PRE-ELABORAZIONE DEI DATI DI TRANSITO ---
    # Applica la mappatura dello stato e la formattazione del nome
    df_transito['Stato_Mappato'] = df_transito['Stato'].map(status_mapping).fillna(df_transito['Stato'])
    df_transito['Cognome_Maiuscolo'] = df_transito['Tecnico'].apply(
        lambda x: str(x).split()[-1].upper() if isinstance(x, str) and ' ' in x else str(x).upper()
    )

    # Crea il dizionario per la ricerca rapida con i dati trasformati
    report_map = {
        str(row['PdL']): {
            'stato': row['Stato_Mappato'],
            'report': row['Report'],
            'tecnico': row['Cognome_Maiuscolo']
        } for _, row in df_transito.iterrows()
    }


    # 2. Aggiorna il database principale usando l'automazione di Excel
    excel = None
    try:
        pythoncom.CoInitialize()
        excel = win32.Dispatch('Excel.Application')
        excel.Visible = False

        abs_path_principale = os.path.abspath(path_principale)
        if not os.path.exists(abs_path_principale):
            raise FileNotFoundError(f"File principale non trovato al percorso: {abs_path_principale}")

        wb = excel.Workbooks.Open(abs_path_principale)
        sheets_to_read = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']

        for sheet_name in sheets_to_read:
            ws = wb.Worksheets(sheet_name)

            header_row = 3
            # Trova dinamicamente gli indici delle colonne target
            pdl_col_idx, stato_col_idx, report_col_idx, personale_col_idx = None, None, None, None
            for i in range(1, ws.UsedRange.Columns.Count + 1):
                header_val = ws.Cells(header_row, i).Value
                if header_val is None: continue
                header_val = str(header_val).strip()
                if header_val == 'PdL':
                    pdl_col_idx = i
                elif header_val == colonna_stato_target:
                    stato_col_idx = i
                elif header_val == colonna_report_target:
                    report_col_idx = i
                elif header_val == colonna_personale_target:
                    personale_col_idx = i

            # Se una delle colonne non viene trovata, passa al foglio successivo
            if not all([pdl_col_idx, stato_col_idx, report_col_idx, personale_col_idx]):
                continue

            # Itera sulle righe dei dati
            for row_idx in range(header_row + 1, ws.UsedRange.Rows.Count + header_row):
                pdl_value = str(ws.Cells(row_idx, pdl_col_idx).Value).strip()
                if pdl_value in report_map:
                    report_data = report_map[pdl_value]

                    # Scrivi i dati mappati nelle colonne corrette
                    ws.Cells(row_idx, stato_col_idx).Value = report_data['stato']
                    ws.Cells(row_idx, report_col_idx).Value = report_data['report']
                    ws.Cells(row_idx, personale_col_idx).Value = report_data['tecnico']

                    aggiornamenti_effettuati += 1
                    del report_map[pdl_value]

            if not report_map: # Se tutti i report sono stati trovati, esci dal loop dei fogli
                break

        wb.Save()
        wb.Close(SaveChanges=False)

    except Exception as e:
        return False, f"Errore durante l'automazione di Excel: {e}"
    finally:
        if excel:
            excel.Quit()
        pythoncom.CoUninitialize()

    # 3. Svuota il file di transito e Google Sheets
    try:
        # Modifica per cancellare solo i valori delle celle, non le righe, per evitare corruzione
        wb = openpyxl.load_workbook(path_transito, keep_vba=True)
        ws = wb.active
        # Itera sulle righe dalla 2 all'ultima
        for row in range(2, ws.max_row + 1):
            # Itera sulle colonne da A a J (da 1 a 10)
            for col in range(1, 11):
                ws.cell(row=row, column=col).value = None
        wb.save(path_transito)

        sheet = client_google.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        header = sheet.row_values(1)
        sheet.clear()
        if header:
            sheet.append_row(header)

        st.cache_data.clear()
        return True, f"Consolidamento completato. {aggiornamenti_effettuati} attività aggiornate. File di transito e Google Sheets sono stati svuotati."

    except Exception as e:
        return False, f"Errore durante la fase di pulizia: {e}"

def carica_report_transito():
    """
    Carica i report solo dal file di transito (Database_Report_Attivita.xlsm).
    """
    storico_path = get_storico_db_path()
    try:
        with config.EXCEL_LOCK:
            df_transito = pd.read_excel(storico_path, sheet_name='Database_Attivita')
        return df_transito
    except FileNotFoundError:
        # Se il file non esiste, restituisce un dataframe vuoto con le colonne corrette
        return pd.DataFrame(columns=['Tecnico', 'PdL', 'Descrizione', 'Stato', 'Report', 'Data_Riferimento'])
    except Exception as e:
        st.error(f"Errore imprevisto durante il caricamento del file di transito: {e}")
        return pd.DataFrame()

def aggiorna_report_transito(df_aggiornato):
    """
    Aggiorna e sovrascrive il file di transito con i dati modificati dall'utente.
    """
    percorso_db = get_storico_db_path()
    success, message = _salva_db_excel(df_aggiornato, percorso_db)

    if success:
        st.cache_data.clear()

    return success, message