import pandas as pd
import sqlite3
import datetime
import os
import sys
import logging
# from openpyxl import load_workbook # Sostituito da win32com
# from openpyxl.utils.dataframe import dataframe_to_rows

try:
    import win32com.client as win32
except ImportError:
    win32 = None
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

# Colonne a sincronizzazione bidirezionale (basate sui nomi DB)
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
        logging.info(f"La colonna timestamp '{EXCEL_TIMESTAMP_COLUMN}' non è presente. Verrà creata con valore di default.")
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
            logging.info(f"'{key}' trovato in Excel ma non nel DB. Inserimento nel DB.")
            row_data = df_excel.loc[key].to_dict()
            row_data[PRIMARY_KEY] = key  # <-- ADD THIS LINE
            row_data[TIMESTAMP_COLUMN] = now
            db_inserts.append(row_data)
        elif is_in_db and not is_in_excel:
            logging.warning(f"'{key}' trovato nel DB ma non in Excel. Sarà rimosso dal DB.")
            # La logica di cancellazione gestirà questo caso dopo la sincronizzazione.
            pass
        elif is_in_excel and is_in_db:
            excel_row, db_row = df_excel.loc[key], df_db.loc[key]
            excel_ts = excel_row.get(TIMESTAMP_COLUMN)
            db_ts = db_row.get(TIMESTAMP_COLUMN)
            if excel_ts.floor('s') > db_ts.floor('s'):
                logging.info(f"'{key}': Excel è più recente. Aggiornamento completo del DB.")
                update_data = excel_row.to_dict()
                update_data[PRIMARY_KEY] = key # <-- ADD THIS LINE
                update_data[TIMESTAMP_COLUMN] = excel_ts # Mantiene il timestamp di Excel
                db_updates.append(update_data)

            elif db_ts.floor('s') > excel_ts.floor('s'):
                logging.info(f"'{key}': DB è più recente. Sincronizzazione mista.")
                # 1. Aggiorna DB con colonne unidirezionali da Excel
                db_mixed_update = {col: excel_row.get(col) for col in unidirectional_columns}
                db_mixed_update[PRIMARY_KEY] = key
                db_mixed_update[TIMESTAMP_COLUMN] = db_ts # Mantiene il timestamp del DB
                db_updates.append(db_mixed_update)

                # 2. Prepara aggiornamento per Excel con colonne bidirezionali da DB
                excel_mixed_update = {col: db_row.get(col) for col in BIDIRECTIONAL_COLUMNS}
                excel_mixed_update[PRIMARY_KEY] = key
                excel_mixed_update[SOURCE_SHEET_COLUMN] = excel_row.get(SOURCE_SHEET_COLUMN)
                excel_mixed_update[TIMESTAMP_COLUMN] = db_ts
                excel_updates.append(excel_mixed_update)

    return db_inserts, db_updates, excel_updates

def commit_to_db(inserts, updates):
    if not inserts and not updates:
        logging.info("Nessun aggiornamento per il database.")
        return 0

    total_ops = 0
    with sqlite3.connect(DB_NAME) as conn:
        try:
            with conn:
                for op_list, op_type in [(inserts, "INSERT"), (updates, "UPDATE")]:
                    if not op_list: continue
                    for row_data in op_list:
                        pk = row_data[PRIMARY_KEY]

                        # Filtra solo le colonne che esistono nella tabella del DB
                        sql_data = {k: v for k, v in row_data.items() if k in DB_COLUMNS or k == PRIMARY_KEY}

                        for key, value in sql_data.items():
                            if pd.isna(value): sql_data[key] = None
                            elif isinstance(value, (datetime.datetime, pd.Timestamp)): sql_data[key] = value.strftime(DATETIME_FORMAT)
                            else: sql_data[key] = str(value)

                        update_data = {k: v for k, v in sql_data.items() if k != PRIMARY_KEY}

                        if op_type == "INSERT":
                            update_data[PRIMARY_KEY] = pk
                            cols = ', '.join(f'"{k}"' for k in update_data.keys())
                            placeholders = ', '.join(['?'] * len(update_data))
                            query = f'INSERT OR IGNORE INTO {DB_TABLE_NAME} ({cols}) VALUES ({placeholders})'
                            conn.execute(query, list(update_data.values()))
                        elif op_type == "UPDATE":
                            set_clause = ', '.join([f'"{k}" = ?' for k in update_data.keys()])
                            query = f'UPDATE {DB_TABLE_NAME} SET {set_clause} WHERE "{PRIMARY_KEY}" = ?'
                            conn.execute(query, list(update_data.values()) + [pk])

                    logging.info(f"Eseguite {len(op_list)} operazioni di {op_type} nel DB.")
                    total_ops += len(op_list)
        except sqlite3.Error as e:
            logging.error(f"Errore durante il commit nel DB: {e}", exc_info=True)
            return -1
    return total_ops

def commit_to_excel(updates):
    """
    Scrive le modifiche sul file Excel .xlsm utilizzando l'automazione COM di Windows
    per garantire l'integrità di macro e codice VBA.
    """
    if not updates:
        logging.info("Nessun aggiornamento per Excel.")
        return 0

    if not win32:
        logging.error("Libreria pywin32 non disponibile. Impossibile scrivere su Excel.")
        return -1

    excel_app = None
    workbook = None
    try:
        excel_app = win32.DispatchEx("Excel.Application")
        excel_app.Visible = False
        excel_app.DisplayAlerts = False

        file_path = os.path.abspath(EXCEL_FILE_NAME)
        workbook = excel_app.Workbooks.Open(file_path)
        logging.info(f"File '{EXCEL_FILE_NAME}' aperto tramite automazione COM.")

        updates_by_sheet = defaultdict(list)
        for update in updates:
            updates_by_sheet[update[SOURCE_SHEET_COLUMN]].append(update)

        total_updated_rows = 0
        for sheet_name, sheet_updates in updates_by_sheet.items():
            try:
                ws = workbook.Sheets(sheet_name)
            except Exception:
                logging.warning(f"Foglio '{sheet_name}' non trovato nel file Excel. Aggiornamenti saltati.")
                continue

            header = [cell.Value for cell in ws.Rows(3).Cells if cell.Value is not None]
            try:
                pdl_col_index = header.index('PdL') + 1
            except ValueError:
                logging.error(f"Colonna 'PdL' non trovata nell'header del foglio '{sheet_name}'.")
                continue

            last_row = ws.Cells(ws.Rows.Count, pdl_col_index).End(-4162).Row # xlUp

            for update in sheet_updates:
                pdl_to_find = update[PRIMARY_KEY]
                found = False
                for row in range(4, last_row + 2): # +2 per sicurezza
                    cell_value = ws.Cells(row, pdl_col_index).Value
                    if cell_value and str(cell_value) == pdl_to_find:
                        logging.info(f"Trovato '{pdl_to_find}' nel foglio '{sheet_name}' alla riga {row}. Aggiornamento in corso...")
                        for db_col, value in update.items():
                            excel_col_name = REVERSE_HEADER_MAP.get(db_col)
                            if excel_col_name in header:
                                col_idx = header.index(excel_col_name) + 1
                                cell = ws.Cells(row, col_idx)
                                if isinstance(value, (datetime.datetime, pd.Timestamp)):
                                    cell.Value = value
                                    cell.NumberFormat = 'DD/MM/YYYY HH:MM:SS'
                                else:
                                    cell.Value = value
                        total_updated_rows += 1
                        found = True
                        break
                if not found:
                    logging.warning(f"PdL '{pdl_to_find}' non trovato nel foglio '{sheet_name}'.")

        workbook.Save()
        logging.info(f"File Excel salvato con {total_updated_rows} righe aggiornate tramite automazione COM.")
        return total_updated_rows

    except Exception as e:
        logging.error(f"Errore durante l'automazione di Excel con win32com: {e}", exc_info=True)
        return -1
    finally:
        if workbook:
            workbook.Close(SaveChanges=False)
        if excel_app:
            excel_app.Quit()
        logging.info("Connessione a Excel chiusa correttamente.")

def delete_rows_from_db(keys_to_delete):
    if not keys_to_delete:
        return 0

    logging.info(f"Rimozione di {len(keys_to_delete)} righe dal DB perché non più presenti in Excel.")
    with sqlite3.connect(DB_NAME) as conn:
        try:
            with conn:
                for key in keys_to_delete:
                    conn.execute(f'DELETE FROM {DB_TABLE_NAME} WHERE "{PRIMARY_KEY}" = ?', (key,))
            return len(keys_to_delete)
        except sqlite3.Error as e:
            logging.error(f"Errore durante la cancellazione di righe dal DB: {e}", exc_info=True)
            return -1

def sincronizza_db_excel():
    if not create_lock():
        return False, "Processo di sincronizzazione già in corso."

    try:
        logging.info("--- INIZIO SINCRONIZZAZIONE BIDIREZIONALE ---")

        # 1. Carica dati
        df_excel = load_data_from_excel()
        if df_excel is None:
            return False, "Impossibile caricare i dati da Excel. Controlla il file e i log."

        df_db = load_data_from_db()
        if df_db is None:
            return False, "Impossibile caricare i dati dal Database. Controlla la connessione e i log."

        # 2. Logica di sincronizzazione
        db_inserts, db_updates, excel_updates = sync_data(df_excel, df_db)

        # 3. Commit su DB
        db_ops = commit_to_db(db_inserts, db_updates)
        if db_ops == -1:
            return False, "Errore critico durante l'aggiornamento del database."

        # 4. Commit su Excel
        excel_ops = commit_to_excel(excel_updates)
        if excel_ops == -1:
            return False, "Errore critico durante l'aggiornamento del file Excel. Potrebbe essere aperto o corrotto."

        # 5. Gestione righe cancellate da Excel
        excel_keys_after_sync = set(df_excel.index)
        db_keys_after_sync = set(load_data_from_db().index)
        deleted_from_excel = db_keys_after_sync - excel_keys_after_sync

        deleted_ops = delete_rows_from_db(list(deleted_from_excel))
        if deleted_ops == -1:
             return False, "Errore durante la rimozione di righe obsolete dal database."

        message = (
            f"Sincronizzazione completata.\n"
            f"- Operazioni sul DB: {db_ops} (insert/update)\n"
            f"- Righe aggiornate in Excel: {excel_ops}\n"
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
        print("Operazione completata con successo.")
    else:
        print("Operazione fallita.")
    print(message)