import pandas as pd
import os
import json
import sqlite3
import config
import datetime
import hashlib
from openpyxl import load_workbook

# --- CONFIGURAZIONE ---
DB_NAME = config.PATH_STORICO_DB
TABLE_NAME = "attivita_programmate"

# Mappatura tra i nomi delle colonne in Excel (chiavi) e nel database (valori).
EXCEL_TO_DB_MAP = {
    'PdL': 'PdL', 'CANTIERE': 'Cantiere', 'IMP.': 'Impianto',
    "DESCRIZIONE\nATTIVITA'": 'Descrizione_Attivita', "STATO\nPdL": 'Stato_PdL',
    "STATO\nATTIVITA'": 'Stato_Attivita', 'LUN': 'Lunedi', 'MAR': 'Martedi',
    'MER': 'Mercoledi', 'GIO': 'Giovedi', 'VEN': 'Venerdi', 'DATA FINE': 'Data_Fine'
}
COLONNE_PIANIFICAZIONE = list(EXCEL_TO_DB_MAP.keys())

def log_conflict(pdl, message):
    """Appende un messaggio di conflitto al file di log."""
    with open("sync_conflicts.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} - PdL {pdl}: {message}\n")

def json_serial(obj):
    """Serializzatore JSON per oggetti non serializzabili di default."""
    if isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def calcola_hash_riga(row, colonne):
    """Calcola un hash SHA256 per una riga di dati basandosi su colonne specifiche."""
    stringa_unificata = "".join(str(row.get(c, '')) for c in colonne)
    return hashlib.sha256(stringa_unificata.encode('utf-8')).hexdigest()

def sincronizza_dati():
    """
    Sincronizza in modo bi-direzionale e granulare i dati tra Excel e il database SQLite,
    con una gestione robusta dei conflitti.
    """
    print("Avvio della sincronizzazione bi-direzionale riprogettata...")
    conn = None
    excel_path = config.get_attivita_programmate_path()

    if not os.path.exists(excel_path):
        return False, f"File Excel non trovato: {excel_path}"

    try:
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Caricamento e Preparazione Dati da Excel
        print("Step 1: Caricamento e preparazione dati da Excel...")
        sheets_to_read = {
            'A1': {'tcl': 'Francesco Naselli', 'area': 'Area 1'}, 'A2': {'tcl': 'Francesco Naselli', 'area': 'Area 2'},
            'A3': {'tcl': 'Ferdinando Caldarella', 'area': 'Area 3'}, 'CTE': {'tcl': 'Ferdinando Caldarella', 'area': 'CTE'},
            'BLENDING': {'tcl': 'Ivan Messina', 'area': 'BLENDING'},
        }
        all_excel_data = []
        for sheet_name, metadata in sheets_to_read.items():
            try:
                df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
                df.columns = [str(col).strip() for col in df.columns]
                df.dropna(subset=['PdL'], inplace=True)
                if df.empty: continue

                df['excel_row_index'] = df.index + 4
                df['excel_sheet_name'] = sheet_name
                df['excel_row_hash'] = df.apply(lambda row: calcola_hash_riga(row, COLONNE_PIANIFICAZIONE), axis=1)
                df['TCL'] = metadata['tcl']
                df['Area'] = metadata['area']
                all_excel_data.append(df)
            except Exception as e:
                print(f"Attenzione: Impossibile leggere foglio '{sheet_name}'. Errore: {e}")

        if not all_excel_data:
            return True, "Nessun dato trovato in Excel."

        df_excel = pd.concat(all_excel_data, ignore_index=True).rename(columns=EXCEL_TO_DB_MAP).set_index('PdL')

        # 2. Caricamento Dati dal Database
        print("Step 2: Caricamento dati dal Database...")
        df_db = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn, index_col='PdL')

        # 3. Logica di Sincronizzazione Granulare
        print("Step 3: Avvio logica di sincronizzazione granulare...")
        cursor.execute("SELECT value FROM sync_metadata WHERE key = 'last_sync_timestamp'")
        last_sync_time = (cursor.fetchone() or ['1970-01-01T00:00:00'])[0]
        now_iso = datetime.datetime.now().isoformat()

        all_pdls = set(df_excel.index) | set(df_db.index)
        updates_to_db, deletions_from_db, additions_to_db = [], [], []
        rows_to_update_in_excel, rows_to_add_to_excel = [], []

        for pdl in all_pdls:
            in_excel, in_db = pdl in df_excel.index, pdl in df_db.index
            excel_row, db_row = (df_excel.loc[pdl] if in_excel else None, df_db.loc[pdl] if in_db else None)

            if in_excel and not in_db: additions_to_db.append(excel_row)
            elif not in_excel and in_db:
                if db_row['row_last_modified'] > last_sync_time: rows_to_add_to_excel.append(db_row)
                else: deletions_from_db.append(pdl)
            elif in_excel and in_db:
                excel_hash_changed = excel_row['excel_row_hash'] != db_row['excel_row_hash']
                app_row_changed = db_row['row_last_modified'] > last_sync_time

                if excel_hash_changed and app_row_changed:
                    log_conflict(pdl, "Modificato in Excel e App. Priorità a pianificazione Excel, mantenendo dati App.")
                    update_values = excel_row[list(EXCEL_TO_DB_MAP.values())].to_dict()
                    update_values.update({'excel_row_hash': excel_row['excel_row_hash'], 'excel_row_index': excel_row['excel_row_index']})
                    updates_to_db.append((update_values, pdl))
                elif excel_hash_changed:
                    updates_to_db.append((excel_row.to_dict(), pdl))
                elif app_row_changed:
                    rows_to_update_in_excel.append(db_row)

        with conn: # Transazione per operazioni su DB
            if additions_to_db:
                df_add = pd.DataFrame(additions_to_db)
                df_add.index.name = 'PdL'
                df_add.reset_index(inplace=True)
                df_add['App_Stato'], df_add['Storico'], df_add['row_last_modified'] = 'Pianificato', '[]', now_iso
                db_cols = [info[1] for info in cursor.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()]
                df_add[[c for c in df_add.columns if c in db_cols]].to_sql(TABLE_NAME, conn, if_exists='append', index=False)
                print(f"  - Aggiunte {len(additions_to_db)} attività al DB.")
            if deletions_from_db:
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE PdL IN ({','.join('?'*len(deletions_from_db))})", tuple(deletions_from_db))
                print(f"  - Cancellate {len(deletions_from_db)} attività dal DB.")
            if updates_to_db:
                for data, pdl in updates_to_db:
                    data.pop('PdL', None); data.pop('excel_sheet_name', None)
                    if 'row_last_modified' not in data: data['row_last_modified'] = now_iso
                    set_clause = ", ".join([f'"{k}" = ?' for k in data.keys()])
                    cursor.execute(f'UPDATE {TABLE_NAME} SET {set_clause} WHERE PdL = ?', list(data.values()) + [pdl])
                print(f"  - Aggiornate {len(updates_to_db)} attività nel DB.")

        rows_to_write = rows_to_update_in_excel + rows_to_add_to_excel
        if rows_to_write:
            print(f"  - Scrittura di {len(rows_to_write)} modifiche su Excel...")
            wb = load_workbook(excel_path, keep_vba=True)
            DB_TO_EXCEL_MAP = {v: k for k, v in EXCEL_TO_DB_MAP.items()}
            area_map = {v['area']: k for k, v in sheets_to_read.items()}

            for db_row in rows_to_update_in_excel:
                ws = wb[db_row['excel_sheet_name']]
                headers = {str(cell.value).strip(): cell.column for cell in ws[3]}
                for db_col, excel_col in DB_TO_EXCEL_MAP.items():
                    if excel_col in headers and db_col in db_row and pd.notna(db_row[db_col]):
                        ws.cell(row=int(db_row['excel_row_index']), column=headers[excel_col]).value = db_row[db_col]
            for db_row in rows_to_add_to_excel:
                sheet_name = area_map.get(db_row.get('Area'))
                if not sheet_name or sheet_name not in wb.sheetnames: continue
                ws = wb[sheet_name]
                headers = [str(cell.value).strip() for cell in ws[3]]
                new_row = [db_row.get(EXCEL_TO_DB_MAP.get(h, h)) for h in headers]
                ws.append(new_row)

            wb.save(excel_path)
            print("  - File Excel salvato.")

            with conn: # Aggiorna hash post-scrittura
                for db_row in rows_to_write:
                    excel_data = {DB_TO_EXCEL_MAP.get(k, k): v for k, v in db_row.items()}
                    new_hash = calcola_hash_riga(excel_data, COLONNE_PIANIFICAZIONE)
                    cursor.execute(f"UPDATE {TABLE_NAME} SET excel_row_hash = ? WHERE PdL = ?", (new_hash, db_row.name))
                print("  - Hash aggiornati nel DB.")

        with conn: # Finalizza la sincronizzazione
            cursor.execute("INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)", ('last_sync_timestamp', now_iso))

        print("Sincronizzazione bi-direzionale completata con successo.")
        return True, "Sincronizzazione completata."

    except Exception as e:
        if conn: conn.rollback()
        import traceback
        traceback.print_exc()
        return False, f"Errore catastrofico durante la sincronizzazione: {e}"
    finally:
        if conn: conn.close()

# Il blocco if __name__ == "__main__" è stato rimosso per garantire
# che questo script venga eseguito solo tramite l'orchestratore run_process.py
# per mantenere la coerenza dell'ambiente. La logica di creazione del file
# di test è ora gestita direttamente dall'orchestratore.