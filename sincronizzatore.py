import pandas as pd
import sqlite3
import datetime
import os
import sys
import logging
from collections import defaultdict
import json
import warnings

# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*."
)

try:
    import win32com.client as win32
    import pythoncom
except ImportError:
    win32 = None
    pythoncom = None
    logging.warning("Libreria pywin32 non trovata. La sincronizzazione con Excel non funzionerà.")

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
DB_TABLE_NAME = "attivita_programmate"
EXCEL_FILE_NAME = "ATTIVITA_PROGRAMMATE.xlsm"
SHEETS_TO_SYNC = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']
PRIMARY_KEY = "PdL"
TIMESTAMP_COLUMN = "row_last_modified"
DB_TIMESTAMP_COLUMN = "db_last_modified"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("sync_log.log", mode='w'), logging.StreamHandler()])

HEADER_MAP = {
    'FERM': 'FERM', 'MANUT': 'MANUT', 'PS': 'PS', 'AREA ': 'AREA', 'PdL': 'PdL',
    'IMP.': 'IMP', 'DESCRIZIONE\nATTIVITA\'': 'DESCRIZIONE_ATTIVITA', 'LUN': 'LUN',
    'MAR': 'MAR', 'MER': 'MER', 'GIO': 'GIO', 'VEN': 'VEN', 'STATO\nPdL': 'STATO_PdL',
    'ESE': 'ESE', 'SAIT': 'SAIT', 'PONTEROSSO': 'PONTEROSSO',
    'STATO\nATTIVITA\'': 'STATO_ATTIVITA', 'DATA\nCONTROLLO': 'DATA_CONTROLLO',
    'PERSONALE\nIMPIEGATO': 'PERSONALE_IMPIEGATO', 'PO': 'PO', 'AVVISO': 'AVVISO',
    "DataUltimaModifica": TIMESTAMP_COLUMN
}
DB_COLUMNS = list(HEADER_MAP.values()) + ['Storico', DB_TIMESTAMP_COLUMN]

def load_data_from_excel():
    """Carica i dati da tutti i fogli Excel e crea uno storico iniziale per le righe completate."""
    all_dfs = []
    for sheet in SHEETS_TO_SYNC:
        try:
            df = pd.read_excel(EXCEL_FILE_NAME, sheet_name=sheet, header=2, engine='openpyxl', dtype=str).where(pd.notnull, None)
            df.dropna(subset=['PdL'], inplace=True)
            df['source_sheet'] = sheet
            all_dfs.append(df)
        except Exception as e:
            logging.warning(f"Impossibile leggere il foglio '{sheet}'. Errore: {e}")

    if not all_dfs: return None

    master_df = pd.concat(all_dfs, ignore_index=True).rename(columns=HEADER_MAP)
    master_df.drop_duplicates(subset=[PRIMARY_KEY], keep='first', inplace=True)
    master_df[TIMESTAMP_COLUMN] = pd.to_datetime(master_df[TIMESTAMP_COLUMN], errors='coerce').fillna(pd.Timestamp.min)

    def create_storico(row):
        if pd.notna(row.get('DATA_CONTROLLO')) and pd.notna(row.get('PERSONALE_IMPIEGATO')):
            try:
                data_riferimento = pd.to_datetime(row['DATA_CONTROLLO'])
                return json.dumps([{
                    "Data_Riferimento_dt": data_riferimento.isoformat(),
                    "Tecnico": row['PERSONALE_IMPIEGATO'],
                    "Report": row.get('STATO_ATTIVITA', 'Nessun report da Excel.'),
                    "Stato": row.get('STATO_PdL')
                }])
            except (ValueError, TypeError):
                return None
        return None

    master_df['Storico'] = master_df.apply(create_storico, axis=1)
    return master_df.set_index(PRIMARY_KEY)

def load_data_from_db():
    """Carica i dati dal database, gestendo correttamente i timestamp nulli."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {DB_TABLE_NAME}", conn, index_col=PRIMARY_KEY,
                                   parse_dates=[TIMESTAMP_COLUMN, DB_TIMESTAMP_COLUMN])
            df[TIMESTAMP_COLUMN] = pd.to_datetime(df[TIMESTAMP_COLUMN], errors='coerce').fillna(pd.Timestamp.min)
            df[DB_TIMESTAMP_COLUMN] = pd.to_datetime(df[DB_TIMESTAMP_COLUMN], errors='coerce').fillna(pd.Timestamp.min)
            return df
    except Exception:
        return pd.DataFrame()

def sync_data(df_excel, df_db):
    """Confronta i dati e determina le operazioni di inserimento e aggiornamento, unendo correttamente lo storico."""
    inserts, updates = [], []
    for pdl, excel_row in df_excel.iterrows():
        if pdl not in df_db.index:
            inserts.append({PRIMARY_KEY: pdl, **excel_row.to_dict()})
        else:
            db_row = df_db.loc[pdl]
            if excel_row[TIMESTAMP_COLUMN] > db_row.get(DB_TIMESTAMP_COLUMN, pd.Timestamp.min):
                update_data = {PRIMARY_KEY: pdl, **excel_row.to_dict()}
                if pd.notna(excel_row.get('Storico')):
                    try:
                        storico_excel = json.loads(excel_row['Storico'])
                        storico_db_json = db_row.get('Storico')
                        storico_db = json.loads(storico_db_json) if pd.notna(storico_db_json) else []

                        # Unisci e deduplica
                        storico_unificato = {item['Data_Riferimento_dt']: item for item in storico_db}
                        for item in storico_excel:
                            storico_unificato[item['Data_Riferimento_dt']] = item

                        update_data['Storico'] = json.dumps(sorted(storico_unificato.values(), key=lambda x: x['Data_Riferimento_dt'], reverse=True))
                    except (json.JSONDecodeError, TypeError):
                        pass
                updates.append(update_data)
    logging.info(f"Operazioni calcolate: {len(inserts)} inserimenti, {len(updates)} aggiornamenti.")
    return inserts, updates

def commit_to_db(inserts, updates):
    """Esegue il commit dei dati nel database, gestendo la conversione dei tipi."""
    if not inserts and not updates: return 0
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        now_iso = datetime.datetime.now().isoformat()

        def sanitize(row):
            sanitized_row = {}
            for k, v in row.items():
                if pd.isna(v): sanitized_row[k] = None
                elif isinstance(v, (datetime.datetime, pd.Timestamp)): sanitized_row[k] = v.isoformat()
                else: sanitized_row[k] = v
            return sanitized_row

        try:
            if inserts:
                insert_data = [{**sanitize(row), DB_TIMESTAMP_COLUMN: now_iso} for row in inserts]
                cols = list(insert_data[0].keys())
                placeholders = ', '.join([f':{k}' for k in cols])
                cursor.executemany(f"INSERT OR IGNORE INTO {DB_TABLE_NAME} ({', '.join(f'\"{c}\"' for c in cols)}) VALUES ({placeholders})", insert_data)

            if updates:
                for row in updates:
                    pk_val = row.pop(PRIMARY_KEY)
                    row[DB_TIMESTAMP_COLUMN] = now_iso
                    sanitized_row = sanitize(row)
                    set_clause = ', '.join(f'"{k}" = ?' for k in sanitized_row.keys())
                    params = list(sanitized_row.values()) + [pk_val]
                    cursor.execute(f'UPDATE {DB_TABLE_NAME} SET {set_clause} WHERE "{PRIMARY_KEY}" = ?', params)
            
            conn.commit()
            return len(inserts) + len(updates)
        except sqlite3.Error as e:
            logging.error(f"Errore durante il commit nel DB: {e}")
            conn.rollback()
            return -1

def sincronizza():
    """Funzione principale che orchestra il processo di sincronizzazione."""
    logging.info("--- INIZIO SINCRONIZZAZIONE ---")
    df_excel = load_data_from_excel()
    if df_excel is None: return False, "Impossibile caricare i dati da Excel."
    
    df_db = load_data_from_db()

    inserts, updates = sync_data(df_excel, df_db)
    db_ops = commit_to_db(inserts, updates)

    if db_ops == -1: return False, "Errore critico durante l'aggiornamento del database."

    message = f"Sincronizzazione completata.\n- Operazioni totali sul DB: {db_ops}"
    logging.info(message)
    return True, message

if __name__ == "__main__":
    success, message = sincronizza()
    print(f"\nRisultato: {'Successo' if success else 'Fallimento'}\n{message}")