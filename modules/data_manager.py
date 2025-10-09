import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading
import openpyxl
import warnings

# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*."
)

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
    Carica tutti i dati gestionali direttamente dal database SQLite in modo thread-safe.
    """
    import sqlite3
    DB_NAME = "schedario.db"

    if not os.path.exists(DB_NAME):
        st.error(f"Database '{DB_NAME}' non trovato. Eseguire lo script di avvio.")
        return None

    conn = None
    try:
        # Acquisisce il lock per prevenire la lettura durante una scrittura in background
        with config.EXCEL_LOCK:
            conn = sqlite3.connect(DB_NAME)

            tabelle = [
                "contatti", "turni", "prenotazioni", "sostituzioni",
                "notifiche", "bacheca", "richieste_materiali", "richieste_assenze", "access_logs"
            ]

            data = {}
            for tabella in tabelle:
                try:
                    data[tabella] = pd.read_sql_query(f"SELECT * FROM {tabella}", conn)
                except pd.io.sql.DatabaseError as e:
                    print(f"Avviso: tabella '{tabella}' non trovata o vuota nel DB. Errore: {e}")
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA table_info({tabella});")
                    columns = [info[1] for info in cursor.fetchall()]
                    data[tabella] = pd.DataFrame(columns=columns)

            if 'turni' in data and 'Tipo' not in data['turni'].columns:
                data['turni']['Tipo'] = 'Assistenza'
            if 'turni' in data:
                 data['turni']['Tipo'] = data['turni']['Tipo'].fillna('Assistenza')

            conn.close()
            conn = None # Evita la doppia chiusura nel blocco finally

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
    import pandas as pd
    DB_NAME = "schedario.db"
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        with config.EXCEL_LOCK:
            for table_name, df in data.items():
                if not isinstance(df, pd.DataFrame):
                    continue

                # Crea una copia per la modifica sicura
                df_to_save = df.copy()

                # Itera su tutte le colonne per convertire i tipi non supportati
                for col in df_to_save.columns:
                    # Converte le colonne di tipo datetime in stringhe ISO 8601
                    if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                        df_to_save[col] = df_to_save[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
                    # Aggiunge un controllo per celle singole che potrebbero essere Timestamp
                    elif df_to_save[col].dtype == 'object':
                        df_to_save[col] = df_to_save[col].apply(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x)

                # Sovrascrive completamente la tabella con i nuovi dati sanificati
                df_to_save.to_sql(table_name, conn, if_exists='replace', index=False)
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
    # Aggiungo la colonna IMP per il filtro
    cols_to_extract = ['PdL', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO', "STATO\nATTIVITA'", "IMP"]

    for sheet_name in sheets_to_read:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            df.columns = [str(col).strip() for col in df.columns]

            # Assicurati che le colonne esistano, altrimenti creale vuote per evitare errori
            if "STATO\nATTIVITA'" not in df.columns:
                df["STATO\nATTIVITA'"] = ""
            if "IMP" not in df.columns:
                df["IMP"] = ""

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

def scrivi_o_aggiorna_risposta(dati_da_scrivere, matricola, data_riferimento):
    """
    Scrive un report direttamente nel database SQLite, aggiornando lo storico,
    lo stato e il timestamp di modifica dell'attività.
    """
    import sqlite3

    azione = "inviato"
    # Utilizza la data di riferimento dell'attività per il timestamp, non la data corrente.
    timestamp = datetime.datetime.combine(data_riferimento, datetime.datetime.min.time())
    data_riferimento_str = data_riferimento.strftime('%d/%m/%Y')

    conn = None
    try:
        conn = sqlite3.connect("schedario.db")
        cursor = conn.cursor()

        # Recupera il nome completo dalla matricola per usarlo nel report e nell'email
        cursor.execute("SELECT \"Nome Cognome\" FROM contatti WHERE Matricola = ?", (str(matricola),))
        user_result = cursor.fetchone()
        if not user_result:
            st.error(f"Impossibile trovare l'utente con matricola {matricola}.")
            return False
        nome_completo = user_result[0]

        descrizione_completa = str(dati_da_scrivere['descrizione'])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        if not pdl_match:
            st.error("Errore: Impossibile estrarre il PdL dalla descrizione.")
            return False
        pdl = pdl_match.group(1)

        nuovo_record_storico = {
            'PdL': pdl,
            'Matricola': str(matricola),
            'Descrizione': dati_da_scrivere['descrizione'],
            'Stato': dati_da_scrivere['stato'],
            'Data_Riferimento': data_riferimento_str,
            'Tecnico': nome_completo,
            'Report': dati_da_scrivere['report'],
            'Data_Compilazione': timestamp.isoformat(),
            'Data_Riferimento_dt': data_riferimento.isoformat()
        }

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
                "UPDATE attivita_programmate SET Storico = ?, STATO_ATTIVITA = ?, STATO_PdL = ?, db_last_modified = ? WHERE PdL = ?",
                (nuovo_storico_json, nuovo_stato, nuovo_stato, db_last_modified_ts, pdl)
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
        </table>
        <br><hr>
        <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
        <p><strong>Gianky Allegretti</strong><br>
        Direttore Tecnico</p>
        </body></html>
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
        if conn:
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

@st.cache_data(ttl=300)
def trova_attivita(matricola, giorno, mese, anno, df_contatti):
    # Funzione interna cachata per caricare il file Excel una sola volta per mese/anno
    @st.cache_data(ttl=3600)
    def _carica_giornaliera_mese(path):
        try:
            return pd.read_excel(path, sheet_name=None, header=None)
        except FileNotFoundError:
            return None
        except Exception as e:
            st.error(f"Errore imprevisto durante la lettura di {path}: {e}")
            return None

    try:
        # --- FASE 1: Trova il nome completo dell'utente dalla matricola ---
        if df_contatti is None or df_contatti.empty:
            st.warning("Dataframe contatti non disponibile per `trova_attivita`.")
            return []

        user_series = df_contatti[df_contatti['Matricola'] == str(matricola)]
        if user_series.empty:
            st.warning(f"Impossibile trovare l'utente con matricola {matricola}.")
            return []
        utente_completo = user_series.iloc[0]['Nome Cognome']

        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")

        # Carica l'intero workbook in memoria (cachato)
        workbook_sheets = _carica_giornaliera_mese(path_giornaliera_mensile)
        if workbook_sheets is None:
            return [] # File non trovato per il mese/anno

        # Trova il nome corretto del foglio per il giorno richiesto
        target_sheet_name = None
        day_str = str(giorno)
        for sheet_name in workbook_sheets.keys():
            if day_str in sheet_name.split():
                target_sheet_name = sheet_name
                break

        if not target_sheet_name:
            return [] # Foglio per il giorno non trovato

        df_giornaliera = workbook_sheets[target_sheet_name]
        df_range = df_giornaliera.iloc[3:45]

        pdls_utente = set()
        for _, riga in df_range.iterrows():
            if 5 < len(riga) and 9 < len(riga):
                nome_in_giornaliera = str(riga[5]).strip()
                if nome_in_giornaliera and _match_partial_name(nome_in_giornaliera, utente_completo):
                    pdl_text = str(riga[9])
                    if not pd.isna(pdl_text):
                        pdls_found = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
                        pdls_utente.update(pdls_found)

        if not pdls_utente:
            return []

        # Ottimizzazione: Carica lo storico una sola volta
        df_storico_db = carica_dati_attivita_programmate()

        attivita_collezionate = {}
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
                    # Filtra lo storico per il PdL corrente
                    storico_pdl = df_storico_db[df_storico_db['PdL'] == pdl].to_dict('records')

                    attivita_collezionate[activity_key] = {
                        'pdl': pdl,
                        'attivita': desc,
                        'storico': storico_pdl[0]['Storico'] if storico_pdl and 'Storico' in storico_pdl[0] else [],
                        'team_members': {}
                    }

                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    for _, contact_row in df_contatti.iterrows():
                        if _match_partial_name(nome_membro, contact_row['Nome Cognome']):
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

    except Exception as e:
        # Evita di mostrare errori se il file non esiste (comportamento atteso per giorni futuri)
        if not isinstance(e, FileNotFoundError):
            st.error(f"Errore durante la ricerca attività per il {giorno}/{mese}/{anno}: {e}")
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