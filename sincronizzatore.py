import pandas as pd
import os
import json
import sqlite3
import config

# --- CONFIGURAZIONE ---
DB_NAME = "schedario.db"
TABLE_NAME = "attivita_programmate"

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

    df_archivio['Report'].fillna("Nessun report disponibile.", inplace=True)
    df_archivio['Data_Compilazione'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')
    df_archivio['Data_Riferimento_dt'] = pd.to_datetime(df_archivio['Data_Riferimento'], errors='coerce')

    return df_archivio

def sincronizza_dati():
    """
    Legge i dati da Excel e li inserisce nel DB, restituendo un risultato.
    Restituisce:
        (bool, str): Tupla con (successo, messaggio_di_stato)
    """
    excel_path = config.get_attivita_programmate_path()

    if not os.path.exists(excel_path):
        msg = f"File attività programmate non trovato: {excel_path}"
        print(f"ERRORE: {msg}")
        return False, msg

    # ... (la logica di lettura da Excel rimane la stessa)
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
        'IN CORSO': 'Aperto', 'DA CHIUDERE': 'Terminata',
        'TERMINATA': 'Terminata', 'SOSPESA': 'Sospeso', 'NON SVOLTA': 'Non Svolta'
    }
    df_storico_full = carica_archivio_completo_locale()

    for sheet_name, metadata in sheets_to_read.items():
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
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
            giorni_programmati = df_filtered[giorni_settimana].apply(lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']), axis=1)
            df_filtered['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')
            df_filtered['Stato'] = df_filtered['Stato_OdL'].apply(lambda x: status_map.get(str(x).strip().upper(), 'Non Definito') if pd.notna(x) else 'Pianificato')
            df_filtered['Storico'] = df_filtered['PdL'].apply(lambda p: df_storico_full[df_storico_full['PdL'] == p].sort_values(by='Data_Riferimento_dt', ascending=False).to_dict('records') if p in df_storico_full['PdL'].values else [])
            all_data.append(df_filtered)
        except Exception as e:
            msg = f"Errore durante l'elaborazione del foglio '{sheet_name}': {e}"
            print(f"ATTENZIONE: {msg}")
            # Non blocchiamo per un singolo foglio fallito, ma continuiamo
            continue

    if not all_data:
        msg = "Nessun dato valido trovato nel file Excel. Sincronizzazione non eseguita."
        print(msg)
        return True, msg # Restituisce True perché non è un errore bloccante

    final_df = pd.concat(all_data, ignore_index=True)
    num_rows = len(final_df)

    final_df['Storico'] = final_df['Storico'].apply(json.dumps)
    colonne_db = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'TCL', 'Area', 'GiorniProgrammati', 'Stato', 'Storico']
    df_per_db = final_df[colonne_db]

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE_NAME};")
        df_per_db.to_sql(TABLE_NAME, conn, if_exists='append', index=False)
        conn.commit()
        msg = f"Database aggiornato con successo con {num_rows} attività."
        print(msg)
        return True, msg
    except sqlite3.Error as e:
        msg = f"Errore SQLite durante la scrittura nel database: {e}"
        print(f"ERRORE: {msg}")
        return False, msg
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sincronizza_dati()