import pandas as pd
import sqlite3
import datetime
import os
import sys
import logging
from collections import defaultdict

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
EXCEL_TIMESTAMP_COLUMN = "DataUltimaModifica"
SOURCE_SHEET_COLUMN = "source_sheet"
LOCK_FILE = "sync.lock"
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("sync_log.log", mode='w'), logging.StreamHandler()]
)

# --- MAPPATURA E COLONNE ---
HEADER_MAP = {
    'FERM': 'FERM', 'MANUT': 'MANUT', 'PS': 'PS', 'AREA ': 'AREA', 'PdL': 'PdL',
    'IMP.': 'IMP', 'DESCRIZIONE\nATTIVITA\'': 'DESCRIZIONE_ATTIVITA', 'LUN': 'LUN',
    'MAR': 'MAR', 'MER': 'MER', 'GIO': 'GIO', 'VEN': 'VEN', 'STATO\nPdL': 'STATO_PdL',
    'ESE': 'ESE', 'SAIT': 'SAIT', 'PONTEROSSO': 'PONTEROSSO',
    'STATO\nATTIVITA\'': 'STATO_ATTIVITA', 'DATA\nCONTROLLO': 'DATA_CONTROLLO',
    'PERSONALE\nIMPIEGATO': 'PERSONALE_IMPIEGATO', 'PO': 'PO', 'AVVISO': 'AVVISO',
    EXCEL_TIMESTAMP_COLUMN: TIMESTAMP_COLUMN,
    SOURCE_SHEET_COLUMN: SOURCE_SHEET_COLUMN
}
REVERSE_HEADER_MAP = {v: k for k, v in HEADER_MAP.items()}
DB_COLUMNS = list(HEADER_MAP.values())

BIDIRECTIONAL_COLUMNS = [
    'STATO_PdL', 'ESE', 'SAIT', 'PONTEROSSO', 'STATO_ATTIVITA',
    'DATA_CONTROLLO', 'PERSONALE_IMPIEGATO'
]

def create_lock():
    if os.path.exists(LOCK_FILE):
        logging.warning("Lock file exists. Impossibile avviare una nuova sincronizzazione.")
        return False
    with open(LOCK_FILE, 'w') as f: f.write(str(os.getpid()))
    logging.info("Lock file creato.")
    return True

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        logging.info("Lock file rimosso.")

def load_data_from_excel():
    all_dfs = []
    logging.info(f"Inizio caricamento dai fogli: {SHEETS_TO_SYNC}")
    for sheet in SHEETS_TO_SYNC:
        try:
            df = pd.read_excel(EXCEL_FILE_NAME, sheet_name=sheet, header=2, engine='openpyxl', dtype=str).where(pd.notnull, None)
            if df.empty or 'PdL' not in df.columns:
                logging.warning(f"Il foglio '{sheet}' è vuoto o non ha la colonna 'PdL'. Sarà saltato.")
                continue
            df.dropna(subset=['PdL'], inplace=True)
            df[SOURCE_SHEET_COLUMN] = sheet
            all_dfs.append(df)
            logging.info(f"Caricate {len(df)} righe dal foglio '{sheet}'.")
        except Exception as e:
            logging.warning(f"Impossibile leggere il foglio '{sheet}'. Errore: {e}")

    if not all_dfs:
        logging.error("Nessun dato valido caricato da Excel.")
        return None

    master_df = pd.concat(all_dfs, ignore_index=True)
    master_df.rename(columns=HEADER_MAP, inplace=True)

    duplicates = master_df[master_df.duplicated(subset=[PRIMARY_KEY], keep=False)]
    if not duplicates.empty:
        logging.warning(f"Trovati PdL duplicati. Verrà mantenuta solo la prima occorrenza. Duplicati: {duplicates[PRIMARY_KEY].tolist()}")
        master_df.drop_duplicates(subset=[PRIMARY_KEY], keep='first', inplace=True)

    if TIMESTAMP_COLUMN not in master_df.columns:
        master_df[TIMESTAMP_COLUMN] = datetime.datetime(2000, 1, 1)
    master_df[TIMESTAMP_COLUMN] = pd.to_datetime(master_df[TIMESTAMP_COLUMN], errors='coerce').fillna(datetime.datetime(2000, 1, 1))

    master_df[PRIMARY_KEY] = master_df[PRIMARY_KEY].astype(str)
    return master_df.set_index(PRIMARY_KEY)

def load_data_from_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            query = f"SELECT * FROM {DB_TABLE_NAME}"
            df = pd.read_sql_query(query, conn, index_col=PRIMARY_KEY, parse_dates=[TIMESTAMP_COLUMN])
            df[TIMESTAMP_COLUMN] = pd.to_datetime(df[TIMESTAMP_COLUMN], errors='coerce').fillna(datetime.datetime(2000, 1, 1))
            return df
    except Exception as e:
        logging.error(f"Errore durante il caricamento dati dal DB: {e}", exc_info=True)
        return None

def sync_data(df_excel, df_db):
    excel_keys, db_keys = set(df_excel.index), set(df_db.index)
    db_inserts, db_updates, excel_updates = [], [], []
    now = datetime.datetime.now()

    all_db_columns = [col for col in DB_COLUMNS if col in df_excel.columns]
    unidirectional_columns = [col for col in all_db_columns if col not in BIDIRECTIONAL_COLUMNS and col != TIMESTAMP_COLUMN]

    for key in excel_keys.union(db_keys):
        is_in_excel, is_in_db = key in excel_keys, key in db_keys

        if is_in_excel and not is_in_db:
            row_data = df_excel.loc[key].to_dict()
            row_data[PRIMARY_KEY] = key
            row_data[TIMESTAMP_COLUMN] = now
            db_inserts.append(row_data)
        elif is_in_db and not is_in_excel:
            pass
        elif is_in_excel and is_in_db:
            excel_row, db_row = df_excel.loc[key], df_db.loc[key]
            excel_ts = excel_row.get(TIMESTAMP_COLUMN)
            db_ts = db_row.get(TIMESTAMP_COLUMN)
            if pd.isna(excel_ts): excel_ts = datetime.datetime(2000, 1, 1)
            if pd.isna(db_ts): db_ts = datetime.datetime(2000, 1, 1)
                
            if excel_ts.floor('s') > db_ts.floor('s'):
                update_data = excel_row.to_dict()
                update_data[PRIMARY_KEY] = key
                update_data[TIMESTAMP_COLUMN] = excel_ts
                db_updates.append(update_data)
            elif db_ts.floor('s') > excel_ts.floor('s'):
                db_mixed_update = {col: excel_row.get(col) for col in unidirectional_columns}
                db_mixed_update[PRIMARY_KEY] = key
                db_mixed_update[TIMESTAMP_COLUMN] = db_ts
                db_updates.append(db_mixed_update)

                excel_mixed_update = {col: db_row.get(col) for col in BIDIRECTIONAL_COLUMNS}
                excel_mixed_update[PRIMARY_KEY] = key
                excel_mixed_update[SOURCE_SHEET_COLUMN] = excel_row.get(SOURCE_SHEET_COLUMN)
                excel_updates.append(excel_mixed_update)

    logging.info(f"Calcolate {len(db_inserts)} inserimenti DB, {len(db_updates)} aggiornamenti DB, {len(excel_updates)} aggiornamenti Excel.")
    return db_inserts, db_updates, excel_updates

def commit_to_db(inserts, updates):
    if not inserts and not updates:
        logging.info("Nessun aggiornamento per il database.")
        return 0
    
    total_ops = 0
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            # --- OTTIMIZZAZIONE INSERT ---
            if inserts:
                insert_data = []
                # Prepara i dati in un formato consistente per executemany
                for row_data in inserts:
                    # Assicurati che tutte le colonne del DB siano presenti
                    full_row = {col: None for col in DB_COLUMNS}
                    full_row.update(row_data)
                    # Converti i tipi
                    for key, value in full_row.items():
                        if pd.isna(value): full_row[key] = None
                        elif isinstance(value, (datetime.datetime, pd.Timestamp)): full_row[key] = value.strftime(DATETIME_FORMAT)
                        else: full_row[key] = str(value)
                    insert_data.append(full_row)
                
                cols = ', '.join(f'"{k}"' for k in DB_COLUMNS)
                placeholders = ', '.join([f':{k}' for k in DB_COLUMNS])
                query = f'INSERT OR IGNORE INTO {DB_TABLE_NAME} ({cols}) VALUES ({placeholders})'
                cursor.executemany(query, insert_data)
                logging.info(f"Eseguite {len(inserts)} operazioni di INSERT in blocco nel DB.")
                total_ops += len(inserts)

            # --- OTTIMIZZAZIONE UPDATE ---
            if updates:
                update_data_list = []
                for row_data in updates:
                    pk = row_data[PRIMARY_KEY]
                    update_values = {}
                    # Prepara solo le colonne da aggiornare
                    for key, value in row_data.items():
                        if key == PRIMARY_KEY: continue
                        if pd.isna(value): update_values[key] = None
                        elif isinstance(value, (datetime.datetime, pd.Timestamp)): update_values[key] = value.strftime(DATETIME_FORMAT)
                        else: update_values[key] = str(value)
                    
                    if update_values: # Solo se c'è qualcosa da aggiornare
                        update_values['pk'] = pk
                        update_data_list.append(update_values)

                # Raggruppa gli update per set di colonne per usare executemany
                grouped_updates = defaultdict(list)
                for data in update_data_list:
                    cols_to_update = tuple(sorted(k for k in data if k != 'pk'))
                    grouped_updates[cols_to_update].append(data)
                
                for cols, data_list in grouped_updates.items():
                    set_clause = ', '.join([f'"{k}" = :{k}' for k in cols])
                    query = f'UPDATE {DB_TABLE_NAME} SET {set_clause} WHERE "{PRIMARY_KEY}" = :pk'
                    cursor.executemany(query, data_list)

                logging.info(f"Eseguite {len(updates)} operazioni di UPDATE in blocco nel DB.")
                total_ops += len(updates)
            
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Errore durante il commit nel DB: {e}", exc_info=True)
            conn.rollback()
            return -1
    return total_ops

def commit_to_excel(updates):
    if not updates:
        logging.info("Nessun aggiornamento per Excel.")
        return 0

    if not win32 or not pythoncom:
        logging.error("Libreria pywin32 non disponibile.")
        return -1

    excel_app = None
    workbook = None
    
    try:
        pythoncom.CoInitialize()
        excel_app = win32.DispatchEx("Excel.Application")
        excel_app.Visible = False
        excel_app.DisplayAlerts = False
        excel_app.ScreenUpdating = False # Disabilita aggiornamento schermo per velocità

        file_path = os.path.abspath(EXCEL_FILE_NAME)
        if not os.path.exists(file_path):
            logging.error(f"File Excel non trovato: {file_path}")
            return -1
            
        workbook = excel_app.Workbooks.Open(file_path, ReadOnly=False)
        logging.info(f"File '{EXCEL_FILE_NAME}' aperto in modalità ottimizzata.")

        updates_by_sheet = defaultdict(list)
        for update in updates:
            updates_by_sheet[update[SOURCE_SHEET_COLUMN]].append(update)

        total_updated_rows = 0
        for sheet_name, sheet_updates in updates_by_sheet.items():
            ws = None
            try:
                ws = workbook.Sheets(sheet_name)
                logging.info(f"Processo il foglio '{sheet_name}' in modalità blocco...")

                # --- OTTIMIZZAZIONE: LETTURA IN BLOCCO ---
                header_row = 3
                first_data_row = 4
                
                last_row = ws.Cells(ws.Rows.Count, 1).End(-4162).Row # xlUp
                last_col = ws.Cells(header_row, ws.Columns.Count).End(-4159).Row # xlToLeft
                
                header = [cell.Value for cell in ws.Range(ws.Cells(header_row, 1), ws.Cells(header_row, last_col))]
                
                try:
                    pdl_col_idx_0based = header.index(PRIMARY_KEY)
                except ValueError:
                    logging.error(f"Colonna '{PRIMARY_KEY}' non trovata nel foglio '{sheet_name}'. Salto.")
                    continue
                
                # Leggi tutta la tabella di dati in un'unica operazione
                data_range = ws.Range(ws.Cells(first_data_row, 1), ws.Cells(last_row, last_col))
                data_array = list(data_range.Value)

                # Crea una mappa per ricerca rapida: Valore PdL -> indice della riga (0-based)
                pdl_to_row_index = {str(row[pdl_col_idx_0based]): i for i, row in enumerate(data_array) if row[pdl_col_idx_0based]}
                
                # --- OTTIMIZZAZIONE: MODIFICA IN MEMORIA ---
                updated_in_sheet = 0
                for update in sheet_updates:
                    pdl_to_find = update[PRIMARY_KEY]
                    row_idx = pdl_to_row_index.get(pdl_to_find)
                    
                    if row_idx is not None:
                        for db_col, value in update.items():
                            if db_col == TIMESTAMP_COLUMN: continue

                            excel_col_name = REVERSE_HEADER_MAP.get(db_col)
                            if excel_col_name in header:
                                try:
                                    col_idx = header.index(excel_col_name)
                                    # Modifica l'array in memoria (velocissimo)
                                    data_array[row_idx][col_idx] = str(value) if value is not None else ''
                                except ValueError:
                                    pass # La colonna non esiste nell'header letto
                        updated_in_sheet += 1
                    else:
                        logging.warning(f"PdL '{pdl_to_find}' non trovato nella mappa del foglio '{sheet_name}'.")
                
                # --- OTTIMIZZAZIONE: SCRITTURA IN BLOCCO ---
                if updated_in_sheet > 0:
                    logging.info(f"Scrittura di {len(data_array)} righe in blocco sul foglio '{sheet_name}'...")
                    data_range.Value = data_array
                    total_updated_rows += updated_in_sheet
                    logging.info("Scrittura in blocco completata.")

            except Exception as sheet_error:
                logging.error(f"Errore durante l'elaborazione del foglio '{sheet_name}': {sheet_error}", exc_info=True)
            finally:
                if ws: del ws

        if total_updated_rows > 0:
            workbook.Save()
            logging.info(f"File Excel salvato con successo. Righe totali con modifiche: {total_updated_rows}.")
        else:
            logging.info("Nessuna riga è stata aggiornata in Excel.")
            
        return total_updated_rows

    except pythoncom.com_error as e:
        logging.error(f"Errore COM specifico durante l'automazione di Excel: {e}", exc_info=True)
        return -1
    except Exception as e:
        logging.error(f"Errore generico durante l'automazione di Excel: {e}", exc_info=True)
        return -1
    finally:
        if excel_app:
            excel_app.ScreenUpdating = True
        if workbook:
            workbook.Close(SaveChanges=False)
        if excel_app:
            excel_app.Quit()
        
        workbook = None
        excel_app = None
        pythoncom.CoUninitialize()
        logging.info("Connessione a Excel e risorse COM rilasciate correttamente.")

def delete_rows_from_db(keys_to_delete):
    if not keys_to_delete:
        return 0

    logging.info(f"Rimozione di {len(keys_to_delete)} righe dal DB perché non più presenti in Excel.")
    with sqlite3.connect(DB_NAME) as conn:
        try:
            with conn:
                placeholders = ','.join('?' for _ in keys_to_delete)
                query = f'DELETE FROM {DB_TABLE_NAME} WHERE "{PRIMARY_KEY}" IN ({placeholders})'
                conn.execute(query, list(keys_to_delete))
            return len(keys_to_delete)
        except sqlite3.Error as e:
            logging.error(f"Errore durante la cancellazione di righe dal DB: {e}", exc_info=True)
            return -1

def sincronizza_db_excel():
    if not create_lock():
        return False, "Processo di sincronizzazione già in corso."

    try:
        logging.info("--- INIZIO SINCRONIZZAZIONE BIDIREZIONALE ---")

        df_excel = load_data_from_excel()
        if df_excel is None: return False, "Impossibile caricare i dati da Excel."

        df_db = load_data_from_db()
        if df_db is None: return False, "Impossibile caricare i dati dal Database."

        db_inserts, db_updates, excel_updates = sync_data(df_excel, df_db)

        db_ops = commit_to_db(db_inserts, db_updates)
        if db_ops == -1: return False, "Errore critico durante l'aggiornamento del database."

        excel_ops = commit_to_excel(excel_updates)
        if excel_ops == -1: return False, "Errore critico durante l'aggiornamento del file Excel."

        df_db_after_sync = load_data_from_db()
        if df_db_after_sync is None: return False, "Impossibile ricaricare lo stato del DB per la pulizia finale."

        deleted_from_excel = set(df_db_after_sync.index) - set(df_excel.index)
        deleted_ops = delete_rows_from_db(list(deleted_from_excel))
        if deleted_ops == -1: return False, "Errore durante la rimozione di righe obsolete dal database."

        message = (
            f"Sincronizzazione completata.\n"
            f"- Operazioni sul DB: {db_ops} (insert/update)\n"
            f"- Righe con modifiche in Excel: {excel_ops}\n"
            f"- Righe rimosse dal DB: {deleted_ops}"
        )
        logging.info(message)
        return True, message

    except Exception as e:
        logging.critical(f"Errore non gestito nel processo di sincronizzazione: {e}", exc_info=True)
        return False, f"Errore non gestito: {e}"
    finally:
        remove_lock()

if __name__ == "__main__":
    success, message = sincronizza_db_excel()
    if success:
        print("\nOperazione completata con successo.")
    else:
        print("\nOperazione fallita.")
    print(message)