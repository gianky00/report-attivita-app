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
    df_archivio['Report'] = df_archivio['Report'].fillna("Nessun report disponibile.")

    # Aggiungi colonne mancanti per compatibilità
    df_archivio['Data_Compilazione'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')
    df_archivio['Data_Riferimento_dt'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')

    return df_archivio

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def scrivi_o_aggiorna_risposta(dati_da_scrivere, nome_completo, data_riferimento):
    """
    Scrive un report direttamente nel database SQLite, aggiornando lo storico,
    lo stato e il timestamp di modifica dell'attività.
    """
    import sqlite3

    azione = "inviato"
    timestamp = datetime.datetime.now()
    data_riferimento_str = data_riferimento.strftime('%d/%m/%Y')

    try:
        descrizione_completa = str(dati_da_scrivere['descrizione'])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        if not pdl_match:
            st.error("Errore: Impossibile estrarre il PdL dalla descrizione.")
            return False
        pdl = pdl_match.group(1)

        nuovo_record_storico = {
            'PdL': pdl,
            'Descrizione': dati_da_scrivere['descrizione'],
            'Stato': dati_da_scrivere['stato'],
            'Data_Riferimento': data_riferimento_str,
            'Tecnico': nome_completo,
            'Report': dati_da_scrivere['report'],
            'Data_Compilazione': timestamp.isoformat(),
            'Data_Riferimento_dt': data_riferimento.isoformat()
        }

        conn = sqlite3.connect("schedario.db")
        cursor = conn.cursor()

        with conn:
            cursor.execute("SELECT Storico FROM attivita_programmate WHERE PdL = ?", (pdl,))
            risultato = cursor.fetchone()

            storico_esistente = json.loads(risultato[0]) if risultato and risultato[0] else []
            storico_esistente.append(nuovo_record_storico)
            storico_esistente.sort(key=lambda x: x.get('Data_Compilazione', ''), reverse=True)

            nuovo_storico_json = json.dumps(storico_esistente, default=json_serial)
            nuovo_stato = dati_da_scrivere['stato']
            db_last_modified_ts = timestamp.isoformat()

            cursor.execute(
                "UPDATE attivita_programmate SET Storico = ?, Stato = ?, db_last_modified = ? WHERE PdL = ?",
                (nuovo_storico_json, nuovo_stato, db_last_modified_ts, pdl)
            )

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
            <tr><th>Data e Ora Invio Report</th><td>{timestamp.strftime('%d/%m/%Y %H:%M:%S')}</td></tr>
            <tr><th>Tecnico</th><td>{nome_completo}</td></tr>
            <tr><th>Attività</th><td>{dati_da_scrivere['descrizione']}</td></tr>
            <tr><th>Stato Finale</th><td><b>{dati_da_scrivere['stato']}</b></td></tr>
            <tr><th>Report Compilato</th><td class="report-content">{report_html}</td></tr>
        </table></body></html>
        """
        invia_email_con_outlook_async(titolo_email, html_body)

        st.cache_data.clear()
        return True

    except sqlite3.Error as e:
        st.error(f"Errore durante l'aggiornamento del database: {e}")
        return False
    except Exception as e:
        st.error(f"Errore imprevisto durante il salvataggio del report: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

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

def consolida_report_giornalieri():
    """
    Consolida in modo intelligente i report dal DB a Excel, aggiornando
    solo i dati modificati basandosi su un timestamp nascosto in Excel.
    """
    import sqlite3
    import win32com.client as win32
    import pythoncom
    from dateutil import parser as date_parser

    path_principale = get_attivita_programmate_path()
    aggiornamenti_effettuati = 0

    colonna_stato_target = "STATO\nPdL"
    colonna_report_target = "STATO\nATTIVITA'"
    colonna_personale_target = "PERSONALE\nIMPIEGATO"
    colonna_timestamp_nascosta = "DB_LAST_CONSOLIDATED"

    status_mapping = {
        'TERMINATA': 'TERMINATA', 'SOSPESA': 'INTERROTTO', 'IN CORSO': 'EMESSO',
        'NON SVOLTA': 'NON SVOLTA'
    }

    report_map = {}
    conn = None
    try:
        conn = sqlite3.connect(config.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT PdL, Storico, db_last_modified FROM attivita_programmate WHERE db_last_modified IS NOT NULL")
        activities = cursor.fetchall()

        if not activities:
            return True, "Nessun report nuovo da consolidare nel database."

        for pdl, storico_json, db_mod_time_str in activities:
            try:
                storico = json.loads(storico_json)
                if not storico: continue
                ultimo_report = storico[0]
                stato_originale = ultimo_report.get('Stato', '')
                report_text = ultimo_report.get('Report', '')
                tecnico_originale = ultimo_report.get('Tecnico', '')
                stato_mappato = status_mapping.get(stato_originale, stato_originale)
                tecnico_formattato = tecnico_originale.split()[-1].upper() if ' ' in str(tecnico_originale) else str(tecnico_originale).upper()
                report_map[pdl] = {
                    'stato': stato_mappato,
                    'report': report_text,
                    'tecnico': tecnico_formattato,
                    'db_last_modified': date_parser.isoparse(db_mod_time_str)
                }
            except (json.JSONDecodeError, IndexError, date_parser.ParserError):
                continue
    except sqlite3.Error as e:
        return False, f"Errore durante la lettura dal database: {e}"
    finally:
        if conn: conn.close()

    if not report_map:
        return True, "Nessun report valido trovato nel database da consolidare."

    excel = None
    try:
        pythoncom.CoInitialize()
        excel = win32.Dispatch('Excel.Application')
        excel.Visible = False
        abs_path_principale = os.path.abspath(path_principale)
        if not os.path.exists(abs_path_principale):
            raise FileNotFoundError(f"File principale non trovato: {abs_path_principale}")

        wb = excel.Workbooks.Open(abs_path_principale)
        sheets_to_read = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']

        for sheet_name in sheets_to_read:
            ws = wb.Worksheets(sheet_name)
            header_row = 3
            header_map = {str(ws.Cells(header_row, i).Value).strip(): i for i in range(1, ws.UsedRange.Columns.Count + 1) if ws.Cells(header_row, i).Value}

            pdl_col_idx = header_map.get('PdL')
            stato_col_idx = header_map.get(colonna_stato_target)
            report_col_idx = header_map.get(colonna_report_target)
            personale_col_idx = header_map.get(colonna_personale_target)

            ts_col_idx = header_map.get(colonna_timestamp_nascosta)
            if not ts_col_idx:
                ts_col_idx = ws.UsedRange.Columns.Count + 1
                ws.Cells(header_row, ts_col_idx).Value = colonna_timestamp_nascosta
                ws.Columns(ts_col_idx).Hidden = True

            if not all([pdl_col_idx, stato_col_idx, report_col_idx, personale_col_idx]): continue

            for row_idx in range(header_row + 1, ws.UsedRange.Rows.Count + 1):
                pdl_value_cell = ws.Cells(row_idx, pdl_col_idx).Value
                if pdl_value_cell is None: continue
                pdl_value = str(pdl_value_cell).strip()

                if pdl_value in report_map:
                    report_data = report_map[pdl_value]
                    excel_ts_val = ws.Cells(row_idx, ts_col_idx).Value
                    excel_ts = None
                    if excel_ts_val:
                        try:
                            excel_ts = date_parser.parse(str(excel_ts_val)).replace(tzinfo=None)
                        except (date_parser.ParserError, TypeError): pass

                    db_mod_time = report_data['db_last_modified'].replace(tzinfo=None)

                    if excel_ts is None or db_mod_time > excel_ts:
                        ws.Cells(row_idx, stato_col_idx).Value = report_data['stato']
                        ws.Cells(row_idx, report_col_idx).Value = report_data['report']
                        ws.Cells(row_idx, personale_col_idx).Value = report_data['tecnico']
                        ws.Cells(row_idx, ts_col_idx).Value = report_data['db_last_modified'].isoformat()
                        aggiornamenti_effettuati += 1

        wb.Save()
        wb.Close(SaveChanges=False)
        st.cache_data.clear()
        return True, f"Consolidamento intelligente completato. {aggiornamenti_effettuati} attività aggiornate in Excel."

    except Exception as e:
        return False, f"Errore durante l'automazione di Excel per il consolidamento: {e}"
    finally:
        if excel:
            excel.Quit()
        pythoncom.CoUninitialize()