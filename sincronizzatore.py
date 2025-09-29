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
    Sincronizza TUTTI i dati (attività e gestionali) dai file Excel al DB.
    Restituisce:
        (bool, str): Tupla con (successo, messaggio_di_stato)
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # --- 1. Sincronizzazione Attività Programmate ---
        excel_path_attivita = config.get_attivita_programmate_path()
        if not os.path.exists(excel_path_attivita):
            raise FileNotFoundError(f"File attività programmate non trovato: {excel_path_attivita}")

        sheets_to_read = {
            'A1': {'tcl': 'Francesco Naselli', 'area': 'Area 1'}, 'A2': {'tcl': 'Francesco Naselli', 'area': 'Area 2'},
            'A3': {'tcl': 'Ferdinando Caldarella', 'area': 'Area 3'}, 'CTE': {'tcl': 'Ferdinando Caldarella', 'area': 'CTE'},
            'BLENDING': {'tcl': 'Ivan Messina', 'area': 'BLENDING'},
        }
        all_data = []
        df_storico_full = carica_archivio_completo_locale()
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
                giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
                giorni_programmati = df_filtered[giorni_settimana].apply(lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']), axis=1)
                df_filtered['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')
                status_map = {
                    'DA EMETTERE': 'Pianificato', 'CHIUSO': 'Completato', 'ANNULLATO': 'Annullato', 'INTERROTTO': 'Sospeso',
                    'RICHIESTO': 'Da processare', 'EMESSO': 'Processato', 'IN CORSO': 'Aperto', 'DA CHIUDERE': 'Terminata',
                    'TERMINATA': 'Terminata', 'SOSPESA': 'Sospeso', 'NON SVOLTA': 'Non Svolta'
                }
                df_filtered['Stato'] = df_filtered['Stato_OdL'].apply(lambda x: status_map.get(str(x).strip().upper(), 'Non Definito') if pd.notna(x) else 'Pianificato')
                df_filtered['Storico'] = df_filtered['PdL'].apply(lambda p: df_storico_full[df_storico_full['PdL'] == p].sort_values(by='Data_Riferimento_dt', ascending=False).to_dict('records') if p in df_storico_full['PdL'].values else [])
                all_data.append(df_filtered)
            except Exception:
                continue

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df['Storico'] = final_df['Storico'].apply(lambda x: json.dumps(x, default=json_serial))
            colonne_db = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'TCL', 'Area', 'GiorniProgrammati', 'Stato', 'Storico']
            df_per_db = final_df[colonne_db]
            cursor.execute(f"DELETE FROM {TABLE_NAME};")
            df_per_db.to_sql(TABLE_NAME, conn, if_exists='append', index=False)

        # --- 2. Sincronizzazione Dati Gestionali ---
        excel_path_gestionale = config.get_gestionale_path()
        if not os.path.exists(excel_path_gestionale):
            raise FileNotFoundError(f"File gestionale non trovato: {excel_path_gestionale}")

        xls = pd.ExcelFile(excel_path_gestionale)
        tabelle_da_sincronizzare = {
            "Contatti": "contatti", "TurniDisponibili": "turni", "Prenotazioni": "prenotazioni",
            "SostituzioniPendenti": "sostituzioni", "Notifiche": "notifiche", "TurniInBacheca": "bacheca",
            "RichiesteMateriali": "richieste_materiali", "RichiesteAssenze": "richieste_assenze"
        }

        for nome_foglio, nome_tabella_db in tabelle_da_sincronizzare.items():
            if nome_foglio in xls.sheet_names:
                df_gest = pd.read_excel(xls, sheet_name=nome_foglio)

                # --- GESTIONE SICURA DELLE PASSWORD PER LA TABELLA CONTATTI ---
                if nome_tabella_db == 'contatti' and 'Password' in df_gest.columns:
                    def hash_password(password):
                        if pd.isna(password) or str(password).strip() == '':
                            return None
                        password_bytes = str(password).encode('utf-8')
                        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
                        return hashed.decode('utf-8')

                    df_gest['PasswordHash'] = df_gest['Password'].apply(hash_password)
                    df_gest = df_gest.drop(columns=['Password'])

                cursor.execute(f"DELETE FROM {nome_tabella_db};")
                df_gest.to_sql(nome_tabella_db, conn, if_exists='append', index=False)

        conn.commit()
        msg = "Sincronizzazione completata con successo per tutti i dati."
        print(msg)
        return True, msg

    except (FileNotFoundError, sqlite3.Error, Exception) as e:
        msg = f"Errore durante la sincronizzazione: {e}"
        print(f"ERRORE: {msg}")
        if conn:
            conn.rollback() # Annulla le modifiche in caso di errore
        return False, msg
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sincronizza_dati()