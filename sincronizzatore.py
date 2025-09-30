import pandas as pd
import sqlite3
import datetime
import os
import sys
import logging
from openpyxl import Workbook

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
DB_TABLE_NAME = "attivita_programmate"
EXCEL_FILE_NAME = "ATTIVITA_PROGRAMMATE.xlsm"
SHEETS_TO_SYNC = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']
OUTPUT_EXCEL_UPDATES_FILE = "AGGIORNAMENTI_DA_DB.xlsx"
PRIMARY_KEY = "PdL"
TIMESTAMP_COLUMN = "row_last_modified"
SOURCE_SHEET_COLUMN = "source_sheet"
LOCK_FILE = "sync.lock"
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT_EXCEL = '%d/%m/%Y'

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("sync_v2.log", mode='w'), logging.StreamHandler()]
)

# --- MAPPATURA HEADER ---
HEADER_MAP = {
    'FERM': 'FERM', 'MANUT': 'MANUT', 'PS': 'PS', 'AREA ': 'AREA', 'PdL': 'PdL',
    'IMP.': 'IMP', 'DESCRIZIONE\nATTIVITA\'': 'DESCRIZIONE_ATTIVITA', 'LUN': 'LUN',
    'MAR': 'MAR', 'MER': 'MER', 'GIO': 'GIO', 'VEN': 'VEN', 'STATO\nPdL': 'STATO_PdL',
    'ESE': 'ESE', 'SAIT': 'SAIT', 'PONTEROSSO': 'PONTEROSSO',
    'STATO\nATTIVITA\'': 'STATO_ATTIVITA', 'DATA\nCONTROLLO': 'DATA_CONTROLLO',
    'PERSONALE\nIMPIEGATO': 'PERSONALE_IMPIEGATO', 'PO': 'PO', 'AVVISO': 'AVVISO',
    'DataUltimaModifica': TIMESTAMP_COLUMN,
    SOURCE_SHEET_COLUMN: SOURCE_SHEET_COLUMN
}
REVERSE_HEADER_MAP = {v: k for k, v in HEADER_MAP.items()}
DB_COLUMNS = list(HEADER_MAP.values()) + ['Storico']

def create_lock():
    if os.path.exists(LOCK_FILE):
        logging.warning("Lock file exists.")
        return False
    with open(LOCK_FILE, 'w') as f: f.write(str(os.getpid()))
    logging.info("Lock file created.")
    return True

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        logging.info("Lock file removed.")

def load_data_from_excel():
    all_dfs = []
    logging.info(f"Inizio caricamento dai fogli: {SHEETS_TO_SYNC}")
    for sheet in SHEETS_TO_SYNC:
        try:
            df = pd.read_excel(EXCEL_FILE_NAME, sheet_name=sheet, header=2, engine='openpyxl', dtype=str).where(pd.notnull, None)
            if df.empty:
                logging.warning(f"Il foglio '{sheet}' è vuoto. Sarà saltato.")
                continue
            df[SOURCE_SHEET_COLUMN] = sheet
            all_dfs.append(df)
            logging.info(f"Letto {len(df)} righe dal foglio '{sheet}'.")
        except Exception as e:
            logging.warning(f"Impossibile leggere il foglio '{sheet}'. Errore: {e}")

    if not all_dfs:
        logging.error("Nessun dato caricato da Excel.")
        return None

    master_df = pd.concat(all_dfs, ignore_index=True)
    master_df.rename(columns=HEADER_MAP, inplace=True)

    master_df.dropna(subset=[PRIMARY_KEY], inplace=True)
    duplicates = master_df[master_df.duplicated(subset=[PRIMARY_KEY], keep=False)]
    if not duplicates.empty:
        logging.warning(f"Trovati {len(duplicates)} PdL duplicati. Verrà mantenuta solo la prima occorrenza. Duplicati: {duplicates[PRIMARY_KEY].tolist()}")
    master_df.drop_duplicates(subset=[PRIMARY_KEY], keep='first', inplace=True)

    if TIMESTAMP_COLUMN not in master_df.columns:
        logging.info(f"Colonna timestamp '{TIMESTAMP_COLUMN}' non trovata in Excel. Verrà creata in memoria con il valore di default.")
        master_df[TIMESTAMP_COLUMN] = "2025-09-30 20:00:00"
    master_df[TIMESTAMP_COLUMN] = pd.to_datetime(master_df[TIMESTAMP_COLUMN], errors='coerce')

    master_df[PRIMARY_KEY] = master_df[PRIMARY_KEY].astype(str)

    return master_df.set_index(PRIMARY_KEY)

def load_data_from_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return pd.read_sql_query(f"SELECT * FROM {DB_TABLE_NAME}", conn, index_col=PRIMARY_KEY, parse_dates=[TIMESTAMP_COLUMN])
    except Exception as e:
        logging.error(f"Errore caricamento dati dal DB: {e}", exc_info=True)
        return None

def sync_data(df_excel, df_db):
    excel_keys, db_keys = set(df_excel.index), set(df_db.index)
    db_inserts, db_updates, excel_actions = [], [], []
    now = datetime.datetime.now()

    for key in excel_keys.union(db_keys):
        is_in_excel, is_in_db = key in excel_keys, key in db_keys

        if is_in_excel and not is_in_db:
            row_data = df_excel.loc[key].to_dict()
            row_data[TIMESTAMP_COLUMN] = now
            db_inserts.append(row_data)
        elif is_in_db and not is_in_excel:
            row_data = df_db.loc[key].to_dict()
            row_data['AZIONE_RICHIESTA'] = 'AGGIUNGERE A EXCEL'
            excel_actions.append(row_data)
        elif is_in_excel and is_in_db:
            excel_row, db_row = df_excel.loc[key], df_db.loc[key]
            excel_ts = pd.to_datetime(excel_row.get(TIMESTAMP_COLUMN), errors='coerce')
            db_ts = pd.to_datetime(db_row.get(TIMESTAMP_COLUMN), errors='coerce')

            # Logica di confronto intelligente
            if pd.isna(excel_ts) and not pd.isna(db_ts):
                are_different = False
                for col in excel_row.index:
                    if col not in [TIMESTAMP_COLUMN, SOURCE_SHEET_COLUMN]:
                        excel_val = str(excel_row.get(col, ''))
                        db_val = str(db_row.get(col, ''))
                        if excel_val != db_val:
                            are_different = True
                            break
                if are_different:
                    row_data = db_row.to_dict()
                    row_data['AZIONE_RICHIESTA'] = 'AGGIORNARE IN EXCEL (Contenuto Diverso)'
                    excel_actions.append(row_data)
            elif not pd.isna(excel_ts) and not pd.isna(db_ts):
                 if excel_ts.floor('s') > db_ts.floor('s'):
                    row_data = excel_row.to_dict()
                    row_data[TIMESTAMP_COLUMN] = excel_ts
                    db_updates.append(row_data)
                 elif db_ts.floor('s') > excel_ts.floor('s'):
                    row_data = db_row.to_dict()
                    row_data['AZIONE_RICHIESTA'] = 'AGGIORNARE IN EXCEL'
                    excel_actions.append(row_data)

        if 'row_data' in locals() and row_data: row_data[PRIMARY_KEY] = key

    if db_inserts or db_updates: commit_to_db(db_inserts, db_updates)
    if excel_actions: export_updates_to_excel(excel_actions)

def commit_to_db(inserts, updates):
    with sqlite3.connect(DB_NAME) as conn:
        try:
            with conn:
                for op_list, op_type in [(inserts, "INSERT"), (updates, "UPDATE")]:
                    if not op_list: continue
                    for row_data in op_list:
                        pk = row_data[PRIMARY_KEY]
                        sql_data = {}
                        for key, value in row_data.items():
                            if key in DB_COLUMNS or key == PRIMARY_KEY:
                                if pd.isna(value): sql_data[key] = None
                                elif isinstance(value, (datetime.datetime, pd.Timestamp)): sql_data[key] = value.strftime(DATETIME_FORMAT)
                                else: sql_data[key] = str(value)

                        update_data = {k: v for k, v in sql_data.items() if k != PRIMARY_KEY}
                        if op_type == "INSERT":
                            update_data[PRIMARY_KEY] = pk
                            cols = ', '.join(f'"{k}"' for k in update_data.keys()); placeholders = ', '.join(['?'] * len(update_data))
                            conn.execute(f"INSERT INTO {DB_TABLE_NAME} ({cols}) VALUES ({placeholders})", list(update_data.values()))
                        elif op_type == "UPDATE":
                            set_clause = ', '.join([f'"{k}" = ?' for k in update_data.keys()])
                            conn.execute(f'UPDATE {DB_TABLE_NAME} SET {set_clause} WHERE "{PRIMARY_KEY}" = ?', list(update_data.values()) + [pk])
                    logging.info(f"Eseguite {len(op_list)} operazioni di {op_type} nel DB.")
        except sqlite3.Error as e: logging.error(f"Errore DB: {e}", exc_info=True)

def export_updates_to_excel(actions):
    if not actions: return
    logging.info(f"Creazione del file di aggiornamento '{OUTPUT_EXCEL_UPDATES_FILE}' con {len(actions)} azioni.")
    df_out = pd.DataFrame(actions)

    if 'DATA_CONTROLLO' in df_out.columns:
        df_out['DATA_CONTROLLO'] = pd.to_datetime(df_out['DATA_CONTROLLO'], errors='coerce').dt.strftime(DATE_FORMAT_EXCEL)

    df_out.rename(columns=REVERSE_HEADER_MAP, inplace=True)

    final_cols = ['AZIONE_RICHIESTA']
    for db_col_name in HEADER_MAP.values():
        excel_header = REVERSE_HEADER_MAP.get(db_col_name)
        if excel_header and excel_header in df_out.columns:
            final_cols.append(excel_header)

    df_out = df_out[[col for col in final_cols if col in df_out.columns]]

    try:
        df_out.to_excel(OUTPUT_EXCEL_UPDATES_FILE, index=False, engine='openpyxl')
        logging.info(f"File '{OUTPUT_EXCEL_UPDATES_FILE}' creato con successo.")
    except Exception as e:
        logging.error(f"Impossibile creare il file di aggiornamento Excel: {e}", exc_info=True)

def main():
    if not create_lock(): sys.exit(1)
    try:
        logging.info("--- Inizio Sincronizzazione v2.2 ---")
        df_excel = load_data_from_excel()
        if df_excel is None: return
        df_db = load_data_from_db()
        if df_db is None: return

        sync_data(df_excel, df_db)

        logging.info("--- Controllo cancellazioni da Excel ---")
        df_excel_after = load_data_from_excel()
        df_db_after = load_data_from_db()
        if df_excel_after is not None and df_db_after is not None:
            excel_keys = set(df_excel_after.index)
            db_keys = set(df_db_after.index)
            deleted_from_excel = db_keys - excel_keys
            if deleted_from_excel:
                logging.info(f"Trovate {len(deleted_from_excel)} righe cancellate da Excel. Rimozione dal DB.")
                with sqlite3.connect(DB_NAME) as conn:
                    for key in deleted_from_excel:
                        conn.execute(f'DELETE FROM {DB_TABLE_NAME} WHERE "{PRIMARY_KEY}" = ?', (key,))

            deleted_from_db = excel_keys - db_keys
            if deleted_from_db:
                logging.info(f"Trovate {len(deleted_from_db)} righe cancellate dal DB. Aggiunte al file di aggiornamento.")
                actions_to_export = [{'AZIONE_RICHIESTA': 'CANCELLARE DA EXCEL', PRIMARY_KEY: key, SOURCE_SHEET_COLUMN: df_excel_after.loc[key, SOURCE_SHEET_COLUMN]} for key in deleted_from_db]
                export_updates_to_excel(actions_to_export)

        logging.info("--- Sincronizzazione Completata ---")
    except Exception as e:
        logging.critical(f"Errore critico nel processo principale: {e}", exc_info=True)
    finally:
        remove_lock()

if __name__ == "__main__":
    main()