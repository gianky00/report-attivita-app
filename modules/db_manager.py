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
                try:
                    data_intervento_iso = pd.to_datetime(row['data_intervento'], format='%d/%m/%Y').isoformat()
                except ValueError:
                    data_intervento_iso = row['data_intervento']

                cursor.execute(
                    """
                    UPDATE relazioni SET
                        data_intervento = ?, tecnico_compilatore = ?, partner = ?,
                        ora_inizio = ?, ora_fine = ?, corpo_relazione = ?, stato = ?,
                        id_validatore = ?, timestamp_validazione = ?
                    WHERE id_relazione = ?
                    """,
                    (
                        data_intervento_iso, row.get('tecnico_compilatore'), row.get('partner'),
                        row.get('ora_inizio'), row.get('ora_fine'), row.get('corpo_relazione'),
                        'Validata', validator_id, datetime.datetime.now().isoformat(),
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

def get_all_relazioni() -> pd.DataFrame:
    """Carica tutte le relazioni dal database, ordinate dalla più recente."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM relazioni ORDER BY timestamp_invio DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare le relazioni: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_archive_filter_options():
    """Recupera i valori unici per i filtri di ricerca dall'archivio."""
    conn = get_db_connection()
    try:
        imp_query = "SELECT DISTINCT IMP FROM attivita_programmate WHERE IMP IS NOT NULL AND IMP != '' ORDER BY IMP"
        impianti = [row['IMP'] for row in conn.execute(imp_query).fetchall()]
        tec_query = """
        SELECT DISTINCT json_extract(value, '$.Tecnico') AS Tecnico
        FROM attivita_programmate, json_each(Storico)
        WHERE Tecnico IS NOT NULL AND Tecnico != ''
        ORDER BY Tecnico;
        """
        tecnici = [row['Tecnico'] for row in conn.execute(tec_query).fetchall()]
        return {'impianti': impianti, 'tecnici': sorted(list(set(tecnici)))}
    except sqlite3.Error as e:
        print(f"Errore nel recuperare le opzioni di filtro: {e}")
        return {'impianti': [], 'tecnici': []}
    finally:
        if conn:
            conn.close()

def get_filtered_archived_activities(pdl_search=None, desc_search=None, imp_search=None, tec_search=None, start_date=None, end_date=None):
    """
    Esegue una ricerca diretta e performante sul database delle attività archiviate.
    Filtra sempre per attività che hanno almeno un intervento nello storico e ordina per data più recente.
    """
    conn = get_db_connection()
    base_query = "SELECT PdL, IMP, DESCRIZIONE_ATTIVITA, Storico FROM attivita_programmate"
    conditions = ["(Storico IS NOT NULL AND Storico != '[]' AND Storico != '')"]
    params = []

    if pdl_search: conditions.append("PdL LIKE ?"); params.append(f"%{pdl_search}%")
    if desc_search: conditions.append("DESCRIZIONE_ATTIVITA LIKE ?"); params.append(f"%{desc_search}%")
    if imp_search: conditions.append(f"IMP IN ({','.join('?' for _ in imp_search)})"); params.extend(imp_search)
    if tec_search: conditions.append(f"EXISTS (SELECT 1 FROM json_each(attivita_programmate.Storico) WHERE json_extract(value, '$.Tecnico') IN ({','.join('?' for _ in tec_search)}))"); params.extend(tec_search)
    if start_date and end_date: conditions.append(f"EXISTS (SELECT 1 FROM json_each(attivita_programmate.Storico) WHERE date(json_extract(value, '$.Data_Riferimento_dt')) BETWEEN date(?) AND date(?))"); params.extend([start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')])

    base_query += " WHERE " + " AND ".join(conditions)

    try:
        df = pd.read_sql_query(base_query, conn, params=params)
        if df.empty: return pd.DataFrame()

        def get_latest_date(json_str):
            try:
                if not json_str: return pd.NaT
                storico = json.loads(json_str)
                if not storico: return pd.NaT
                return max(pd.to_datetime(s.get('Data_Riferimento_dt'), errors='coerce') for s in storico if s.get('Data_Riferimento_dt'))
            except (json.JSONDecodeError, TypeError, ValueError):
                return pd.NaT

        df['latest_date'] = df['Storico'].apply(get_latest_date)
        df.sort_values(by='latest_date', ascending=False, inplace=True, na_position='last')
        df['Storico'] = df['Storico'].apply(lambda x: json.loads(x) if x else [])
        return df.drop(columns=['latest_date'])
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore durante la ricerca filtrata delle attività: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# Altre funzioni (create_validation_session, etc.) sono omesse per brevità perché non pertinenti alla correzione.
def create_validation_session(user_matricola: str, data: list) -> str: return ""
def get_active_validation_session(user_matricola: str) -> dict: return {}
def update_validation_session_data(session_id: str, new_data: list): pass
def delete_validation_session(session_id: str): pass
def get_unvalidated_reports(): return []
def process_and_commit_validated_reports(validated_data: list): pass
def get_interventions_for_technician(technician_matricola: str, start_date, end_date) -> pd.DataFrame: return pd.DataFrame()
def get_technician_performance_data(start_date, end_date) -> pd.DataFrame: return pd.DataFrame()
def get_on_call_shifts_for_period(start_date, end_date) -> pd.DataFrame: return pd.DataFrame()
def salva_relazione(dati_relazione: dict) -> bool: return False
def get_filtered_activities(filters: dict) -> pd.DataFrame: return pd.DataFrame()