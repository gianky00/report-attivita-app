import sqlite3
import pandas as pd
import os
import json
import streamlit as st

DB_NAME = "schedario.db"

def get_db_connection():
    """Crea e restituisce una connessione al database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_shifts_by_type(shift_type: str) -> pd.DataFrame:
    """Carica i turni di un tipo specifico direttamente dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM turni WHERE Tipo = ? ORDER BY Data DESC"
        df = pd.read_sql_query(query, conn, params=(shift_type,))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i turni per tipo '{shift_type}': {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def process_and_commit_validated_relazioni(validated_df: pd.DataFrame, validator_id: str) -> bool:
    """Processa le relazioni validate, aggiornandole nel DB."""
    import datetime
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            for _, row in validated_df.iterrows():
                # Ricostruisci la data di intervento dal formato stringa
                try:
                    data_intervento_iso = pd.to_datetime(row['data_intervento'], format='%d/%m/%Y').isoformat()
                except ValueError:
                    data_intervento_iso = row['data_intervento'] # Mantieni il formato se non è valido

                cursor.execute(
                    """
                    UPDATE relazioni SET
                        data_intervento = ?,
                        tecnico_compilatore = ?,
                        partner = ?,
                        ora_inizio = ?,
                        ora_fine = ?,
                        corpo_relazione = ?,
                        stato = ?,
                        id_validatore = ?,
                        timestamp_validazione = ?
                    WHERE id_relazione = ?
                    """,
                    (
                        data_intervento_iso,
                        row.get('tecnico_compilatore'),
                        row.get('partner'),
                        row.get('ora_inizio'),
                        row.get('ora_fine'),
                        row.get('corpo_relazione'),
                        'Validata', # Imposta lo stato a Validata
                        validator_id,
                        datetime.datetime.now().isoformat(),
                        row['id_relazione']
                    )
                )
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio delle relazioni validate: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_unvalidated_relazioni() -> pd.DataFrame:
    """Carica le relazioni in attesa di validazione ('Inviata')."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM relazioni WHERE stato = 'Inviata' ORDER BY timestamp_invio ASC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare le relazioni da validare: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_reports_to_validate() -> pd.DataFrame:
    """Carica tutti i report in attesa di validazione dalla tabella dedicata."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_da_validare ORDER BY data_compilazione ASC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i report da validare: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def delete_reports_by_ids(report_ids: list) -> bool:
    """Cancella una lista di report dalla tabella di validazione."""
    if not report_ids:
        return True
    conn = get_db_connection()
    try:
        with conn:
            placeholders = ','.join('?' for _ in report_ids)
            query = f"DELETE FROM report_da_validare WHERE id_report IN ({placeholders})"
            conn.execute(query, report_ids)
        return True
    except sqlite3.Error as e:
        print(f"Errore durante la cancellazione dei report: {e}")
        return False
    finally:
        if conn:
            conn.close()

def process_and_commit_validated_reports(validated_data: list) -> bool:
    """
    Salva i report validati nella tabella `report_interventi` del database
    e poi li rimuove dalla tabella di validazione.
    """
    if not validated_data:
        return True

    # 1. Salva i report validati nella tabella 'report_interventi'
    import datetime
    for report_dict in validated_data:
        report_data = {
            "id_report": report_dict.get('id_report'),
            "pdl": report_dict.get('pdl'),
            "descrizione_attivita": report_dict.get('descrizione_attivita'),
            "matricola_tecnico": report_dict.get('matricola_tecnico'),
            "nome_tecnico": report_dict.get('nome_tecnico'),
            "stato_attivita": "Validato", # Sovrascrive lo stato
            "testo_report": report_dict.get('testo_report'),
            "data_compilazione": report_dict.get('data_compilazione'),
            "data_riferimento_attivita": report_dict.get('data_riferimento_attivita'),
            "timestamp_validazione": datetime.datetime.now().isoformat()
        }
        if not salva_report_intervento(report_data):
            # Se il salvataggio nel DB fallisce, logga l'errore ma non bloccare la validazione degli altri report
            print(f"ATTENZIONE: Report {report_dict.get('id_report')} non salvato nel DB storico 'report_interventi'.")

    # 2. Infine, rimuovi i report dalla tabella di validazione
    report_ids_to_delete = [report['id_report'] for report in validated_data]
    if not delete_reports_by_ids(report_ids_to_delete):
        print("ERRORE CRITICO: I report sono stati salvati nel DB storico, ma non è stato possibile rimuoverli dalla coda di validazione.")
        return False

    return True

def salva_report_intervento(dati_report: dict) -> bool:
    """Salva un report di intervento validato nel database."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_report.keys())
            placeholders = ', '.join('?' for _ in dati_report)
            sql = f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_report.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio del report di intervento nel DB: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_validated_intervention_reports() -> pd.DataFrame:
    """Carica tutti i report di intervento validati dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report di intervento: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_validated_reports(table_name: str) -> pd.DataFrame:
    """
    Carica i dati validati da una tabella specifica (es. 'relazioni').
    """
    conn = get_db_connection()
    try:
        # Costruisce la query in modo sicuro per evitare SQL injection sul nome della tabella
        if table_name not in ['relazioni', 'report_validati']: # Whitelist delle tabelle consentite
            raise ValueError("Nome tabella non valido")

        query = f"SELECT * FROM {table_name} WHERE stato = 'Validata' ORDER BY data_intervento DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError, ValueError) as e:
        st.error(f"Errore nel caricamento dei dati dalla tabella {table_name}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def salva_storico_materiali(dati_richiesta: dict) -> bool:
    """Salva una richiesta di materiali approvata nello storico."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_richiesta.keys())
            placeholders = ', '.join('?' for _ in dati_richiesta)
            sql = f"INSERT INTO storico_richieste_materiali ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_richiesta.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della richiesta materiali nello storico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def salva_storico_assenze(dati_richiesta: dict) -> bool:
    """Salva una richiesta di assenza approvata nello storico."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_richiesta.keys())
            placeholders = ', '.join('?' for _ in dati_richiesta)
            sql = f"INSERT INTO storico_richieste_assenze ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_richiesta.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della richiesta assenze nello storico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_storico_richieste_materiali() -> pd.DataFrame:
    """Carica lo storico delle richieste di materiali dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM storico_richieste_materiali ORDER BY timestamp_approvazione DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dello storico materiali: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_storico_richieste_assenze() -> pd.DataFrame:
    """Carica lo storico delle richieste di assenze dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM storico_richieste_assenze ORDER BY timestamp_approvazione DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dello storico assenze: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def salva_relazione(dati_relazione: dict) -> bool:
    """Salva una nuova relazione nel database."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_relazione.keys())
            placeholders = ', '.join('?' for _ in dati_relazione)
            sql = f"INSERT INTO relazioni ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_relazione.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della relazione nel DB: {e}")
        return False
    finally:
        if conn:
            conn.close()
def get_validated_intervention_reports(matricola_tecnico: str = None) -> pd.DataFrame:
    """
    Carica i report di intervento validati dal database.
    Se matricola_tecnico è fornita, filtra per quel tecnico.
    """
    conn = get_db_connection()
    try:
        if matricola_tecnico:
            query = "SELECT * FROM report_interventi WHERE matricola_tecnico = ? ORDER BY data_riferimento_attivita DESC"
            df = pd.read_sql_query(query, conn, params=(matricola_tecnico,))
        else:
            query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
            df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report di intervento: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def save_table_data(df: pd.DataFrame, table_name: str):
    """Salva un DataFrame in una tabella del database, sostituendo i dati esistenti."""
    conn = get_db_connection()
    try:
        # Basic validation to prevent SQL injection on table_name
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")

        # Use 'replace' to drop the old table and create a new one with the df data
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante il salvataggio dei dati nella tabella {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_table_data(table_name: str) -> pd.DataFrame:
    """Carica tutti i dati da una tabella specifica."""
    conn = get_db_connection()
    try:
        # Basic validation to prevent SQL injection on table_name
        if not table_name.isalnum() and '_' not in table_name:
             raise ValueError("Nome tabella non valido.")
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError, ValueError) as e:
        print(f"Errore nel caricare i dati dalla tabella {table_name}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_table_names() -> list:
    """Restituisce una lista con i nomi di tutte le tabelle nel database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    except sqlite3.Error as e:
        print(f"Errore nel recuperare i nomi delle tabelle: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_report_by_id(report_id: str, table_name: str) -> dict:
    """Recupera un singolo report da una tabella specifica per ID."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        query = f"SELECT * FROM {table_name} WHERE id_report = ?"
        cursor = conn.cursor()
        cursor.execute(query, (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore nel recuperare il report {report_id} da {table_name}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_report_by_id(report_id: str, table_name: str) -> bool:
    """Cancella un singolo report da una tabella specifica per ID."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        with conn:
            query = f"DELETE FROM {table_name} WHERE id_report = ?"
            conn.execute(query, (report_id,))
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante la cancellazione del report {report_id} da {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def insert_report(report_data: dict, table_name: str) -> bool:
    """Inserisce i dati di un report in una tabella specifica."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        with conn:
            cols = ', '.join(f'"{k}"' for k in report_data.keys())
            placeholders = ', '.join('?' for _ in report_data)
            sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(report_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'inserimento del report in {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def move_report_atomically(report_data: dict, source_table: str, dest_table: str) -> bool:
    """Sposta un report da una tabella all'altra in modo atomico."""
    conn = get_db_connection()
    try:
        if not all(isinstance(name, str) and (name.isalnum() or '_' in name) for name in [source_table, dest_table]):
            raise ValueError("Nomi delle tabelle non validi.")

        with conn:
            # 1. Delete from source
            delete_query = f"DELETE FROM {source_table} WHERE id_report = ?"
            conn.execute(delete_query, (report_data['id_report'],))

            # 2. Insert into destination
            cols = ', '.join(f'"{k}"' for k in report_data.keys())
            placeholders = ', '.join('?' for _ in report_data)
            insert_query = f"INSERT INTO {dest_table} ({cols}) VALUES ({placeholders})"
            conn.execute(insert_query, list(report_data.values()))
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante lo spostamento atomico del report: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_unvalidated_reports_by_technician(matricola_tecnico: str) -> pd.DataFrame:
    """Carica i report inviati da un tecnico ma non ancora validati."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_da_validare WHERE matricola_tecnico = ? ORDER BY data_compilazione DESC"
        df = pd.read_sql_query(query, conn, params=(matricola_tecnico,))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report non validati per il tecnico {matricola_tecnico}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()
