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
    Sincronizza SOLO i dati delle attività programmate da Excel al DB.
    Questa operazione è distruttiva: sovrascrive la tabella delle attività.
    Restituisce: (bool, str) con successo e messaggio di stato.
    """
    conn = None
    try:
        # --- 1. CARICAMENTO DATI DA EXCEL ---
        excel_path_attivita = config.get_attivita_programmate_path()
        if not os.path.exists(excel_path_attivita):
            raise FileNotFoundError(f"File delle attività programmate non trovato: {excel_path_attivita}")

        df_storico_full = carica_archivio_completo_locale()

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

        final_df = pd.concat(all_data, ignore_index=True)

        # --- 2. TRASFORMAZIONE DATI OTTIMIZZATA ---
        giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
        giorni_programmati = final_df[giorni_settimana].apply(
            lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']),
            axis=1
        )
        final_df['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')

        status_map = {
            'DA EMETTERE': 'Pianificato', 'CHIUSO': 'Completato', 'ANNULLATO': 'Annullato',
            'INTERROTTO': 'Sospeso', 'RICHIESTO': 'Da processare', 'EMESSO': 'Processato',
            'IN CORSO': 'Aperto', 'DA CHIUDERE': 'Terminata', 'TERMINATA': 'Terminata',
            'SOSPESA': 'Sospeso', 'NON SVOLTA': 'Non Svolta'
        }
        final_df['Stato'] = final_df['Stato_OdL'].apply(
            lambda x: status_map.get(str(x).strip().upper(), 'Non Definito') if pd.notna(x) else 'Pianificato'
        )

        # Logica di arricchimento storico VETTORIZZATA
        if not df_storico_full.empty:
            df_storico_full = df_storico_full.sort_values(by='Data_Riferimento_dt', ascending=False)
            storico_grouped = df_storico_full.groupby('PdL').apply(lambda x: x.to_dict('records')).rename('Storico')
            final_df = final_df.merge(storico_grouped, on='PdL', how='left')
            final_df['Storico'] = final_df['Storico'].apply(lambda d: d if isinstance(d, list) else [])
        else:
            final_df['Storico'] = [[] for _ in range(len(final_df))]

        final_df['Storico'] = final_df['Storico'].apply(lambda x: json.dumps(x, default=json_serial))
        colonne_db = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'TCL', 'Area', 'GiorniProgrammati', 'Stato', 'Storico']
        df_per_db = final_df[colonne_db]

        # --- 3. SCRITTURA ATOMICA SUL DATABASE ---
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        with conn:
            cursor.execute(f"DELETE FROM {TABLE_NAME};")
            df_per_db.to_sql(TABLE_NAME, conn, if_exists='append', index=False)

        msg = f"Sincronizzazione delle attività completata con successo. Aggiornate {len(df_per_db)} attività."
        print(msg)
        return True, msg

    except (FileNotFoundError, sqlite3.Error, Exception) as e:
        msg = f"Errore durante la sincronizzazione delle attività: {e}"
        print(f"ERRORE: {msg}")
        return False, msg
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sincronizza_dati()