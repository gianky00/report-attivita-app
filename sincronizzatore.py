import pandas as pd
import os
import json
import sqlite3
import config
import datetime
import bcrypt

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def carica_archivio_completo_locale():
    """
    Versione locale di carica_archivio_completo per evitare import problematici.
    Carica lo storico direttamente dal file ATTIVITA_PROGRAMMATE.xlsx.
    """
    excel_path = config.get_attivita_programmate_path()
    all_data = []

    sheets_to_read = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']
    cols_to_extract = ['PdL', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO', "STATO\nATTIVITA'"]

    for sheet_name in sheets_to_read:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            df.columns = [str(col).strip() for col in df.columns]

            if "STATO\nATTIVITA'" not in df.columns:
                df["STATO\nATTIVITA'"] = ""

            # Controlla solo le colonne essenziali che devono esistere
            essential_cols = ['PdL', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO']
            if all(col in df.columns for col in essential_cols):
                df_sheet = df[cols_to_extract].copy()
                all_data.append(df_sheet)
        except Exception:
            continue

    if not all_data:
        return pd.DataFrame(columns=['PdL', 'Descrizione', 'Stato', 'Data_Riferimento', 'Tecnico', 'Report', 'Data_Compilazione', 'Data_Riferimento_dt'])

    df_archivio = pd.concat(all_data, ignore_index=True)
    df_archivio.dropna(subset=['PdL', 'DATA\nCONTROLLO'], inplace=True)

    df_archivio.rename(columns={
        "DESCRIZIONE\nATTIVITA'": "Descrizione",
        "STATO\nPdL": "Stato",
        "DATA\nCONTROLLO": "Data_Riferimento",
        "PERSONALE\nIMPIEGATO": "Tecnico",
        "STATO\nATTIVITA'": "Report"
    }, inplace=True)

    df_archivio['Report'] = df_archivio['Report'].fillna("Nessun report disponibile.")
    df_archivio['Data_Compilazione'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')
    df_archivio['Data_Riferimento_dt'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')

    return df_archivio

def sincronizza_dati():
    """
    Sincronizza in modo intelligente i dati delle attività da Excel al DB,
    aggiornando solo i record necessari basandosi sui timestamp.
    Non sovrascrive i dati inseriti dall'applicazione (Stato, Storico).
    """
    conn = None
    excel_path_attivita = config.get_attivita_programmate_path()
    if not os.path.exists(excel_path_attivita):
        return False, f"File delle attività programmate non trovato: {excel_path_attivita}"

    try:
        # 1. Controlla i timestamp per vedere se la sincronizzazione è necessaria
        excel_mod_time = os.path.getmtime(excel_path_attivita)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM sync_metadata WHERE key = 'last_excel_sync_timestamp'")
        result = cursor.fetchone()
        last_sync_time = float(result[0]) if result else 0.0

        if excel_mod_time <= last_sync_time:
            msg = "Database già aggiornato con l'ultima versione del file Excel."
            print(msg)
            return True, msg

        # 2. Carica i dati da Excel (la fonte autoritativa per la pianificazione)
        sheets_to_read = {
            'A1': {'tcl': 'Francesco Naselli', 'area': 'Area 1'}, 'A2': {'tcl': 'Francesco Naselli', 'area': 'Area 2'},
            'A3': {'tcl': 'Ferdinando Caldarella', 'area': 'Area 3'}, 'CTE': {'tcl': 'Ferdinando Caldarella', 'area': 'CTE'},
            'BLENDING': {'tcl': 'Ivan Messina', 'area': 'BLENDING'},
        }
        all_data = []
        for sheet_name, metadata in sheets_to_read.items():
            try:
                df = pd.read_excel(excel_path_attivita, sheet_name=sheet_name, header=2)
                df.columns = [str(col).strip() for col in df.columns]
                required_cols = ['PdL', 'IMP.', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'LUN', 'MAR', 'MER', 'GIO', 'VEN']
                if not all(col in df.columns for col in required_cols): continue
                df = df.dropna(subset=['PdL'])
                if df.empty: continue
                df_filtered = df[required_cols].copy()
                df_filtered.columns = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì']
                df_filtered['PdL'] = df_filtered['PdL'].astype(str)
                df_filtered['TCL'] = metadata['tcl']
                df_filtered['Area'] = metadata['area']
                all_data.append(df_filtered)
            except Exception:
                continue

        if not all_data:
            return True, "Nessun dato di attività trovato in Excel da sincronizzare."

        df_excel = pd.concat(all_data, ignore_index=True).set_index('PdL')

        giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
        giorni_programmati = df_excel[giorni_settimana].apply(
            lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']), axis=1
        )
        df_excel['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')

        # 3. Carica i dati esistenti dal DB per confronto
        df_db = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn, index_col='PdL')

        # 4. Esegui la sincronizzazione intelligente
        excel_pdls = set(df_excel.index)
        db_pdls = set(df_db.index)

        pdls_to_add = excel_pdls - db_pdls
        pdls_to_delete = db_pdls - excel_pdls
        pdls_to_check = excel_pdls.intersection(db_pdls)

        with conn:
            if pdls_to_delete:
                placeholders = ','.join('?' for _ in pdls_to_delete)
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE PdL IN ({placeholders})", tuple(pdls_to_delete))

            if pdls_to_add:
                df_to_add = df_excel.loc[list(pdls_to_add)].copy()
                df_to_add['Stato'] = 'Pianificato'
                df_to_add['Storico'] = '[]'
                df_to_add['db_last_modified'] = None
                df_to_add = df_to_add.reset_index()[['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'TCL', 'Area', 'GiorniProgrammati', 'Stato', 'Storico', 'db_last_modified']]
                df_to_add.to_sql(TABLE_NAME, conn, if_exists='append', index=False)

            updates_count = 0
            cols_to_compare = ['Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'TCL', 'Area', 'GiorniProgrammati']
            df_excel_check = df_excel.loc[list(pdls_to_check)][cols_to_compare].fillna('')
            df_db_check = df_db.loc[list(pdls_to_check)][cols_to_compare].fillna('')

            ne_stacked = (df_excel_check != df_db_check).stack()
            changed = ne_stacked[ne_stacked]
            pdls_to_update = changed.index.get_level_values(0).unique().tolist()

            if pdls_to_update:
                for pdl in pdls_to_update:
                    row_to_update = df_excel.loc[pdl]
                    cursor.execute(f"""
                        UPDATE {TABLE_NAME} SET
                            Impianto = ?, Descrizione = ?, Stato_OdL = ?, Lunedì = ?, Martedì = ?,
                            Mercoledì = ?, Giovedì = ?, Venerdì = ?, TCL = ?, Area = ?, GiorniProgrammati = ?
                        WHERE PdL = ?
                    """, (
                        row_to_update['Impianto'], row_to_update['Descrizione'], row_to_update['Stato_OdL'],
                        row_to_update['Lunedì'], row_to_update['Martedì'], row_to_update['Mercoledì'],
                        row_to_update['Giovedì'], row_to_update['Venerdì'], row_to_update['TCL'],
                        row_to_update['Area'], row_to_update['GiorniProgrammati'], pdl
                    ))
                updates_count = len(pdls_to_update)

            cursor.execute("INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)",
                           ('last_excel_sync_timestamp', str(excel_mod_time)))

        total_changes = len(pdls_to_add) + len(pdls_to_delete) + updates_count
        if total_changes > 0:
            msg = f"Sincronizzazione intelligente completata: {len(pdls_to_add)} aggiunte, {updates_count} aggiornate, {len(pdls_to_delete)} rimosse."
        else:
            msg = "Nessuna modifica alla pianificazione rilevata. Il database è già sincronizzato."

        print(msg)
        return True, msg

    except (FileNotFoundError, sqlite3.Error, Exception) as e:
        msg = f"Errore durante la sincronizzazione intelligente: {e}"
        print(f"ERRORE: {msg}")
        return False, msg
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sincronizza_dati()