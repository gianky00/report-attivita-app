"""
Funzioni database per la gestione di report attività e relazioni di reperibilità.
Gestisce il flusso di validazione e la persistenza dei report finali.
"""
import datetime
import sqlite3
from typing import List, Dict, Optional, Any

import pandas as pd
from src.core.database import DatabaseEngine
from src.core.logging import get_logger, measure_time

logger = get_logger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Restituisce una connessione al database core."""
    return DatabaseEngine.get_connection()

@measure_time
def get_reports_to_validate() -> pd.DataFrame:
    """Recupera tutti i report tecnici in attesa di validazione."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM report_da_validare", conn)
    finally:
        conn.close()

def delete_reports_by_ids(report_ids: List[str]) -> bool:
    """Elimina definitivamente un set di report dalla coda di validazione."""
    if not report_ids:
        return True
    placeholders = ", ".join("?" for _ in report_ids)
    sql = f"DELETE FROM report_da_validare WHERE id_report IN ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(report_ids))

def process_and_commit_validated_reports(reports: List[Dict[str, Any]]) -> bool:
    """Sposta i report validati dalla coda alla tabella definitiva in modo transazionale."""
    conn = get_db_connection()
    now = datetime.datetime.now().isoformat()
    try:
        with conn:
            for r in reports:
                r["timestamp_validazione"] = now
                cols = ", ".join(f'"{k}"' for k in r.keys())
                placeholders = ", ".join("?" for _ in r)
                sql_ins = (
                    f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"
                )
                conn.execute(sql_ins, tuple(r.values()))
                conn.execute(
                    "DELETE FROM report_da_validare WHERE id_report = ?",
                    (r["id_report"],),
                )
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore validazione report: {e}")
        return False
    finally:
        conn.close()

def get_unvalidated_relazioni() -> pd.DataFrame:
    """Recupera le relazioni di reperibilità inviate ma non ancora validate."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM relazioni WHERE stato = 'Inviata'", conn
        )
    finally:
        conn.close()

def process_and_commit_validated_relazioni(df: pd.DataFrame, admin_id: str) -> bool:
    """Aggiorna lo stato delle relazioni validate memorizzando il validatore."""
    conn = get_db_connection()
    now = datetime.datetime.now().isoformat()
    try:
        with conn:
            for _, row in df.iterrows():
                sql_upd = "UPDATE relazioni SET stato = 'Validata', id_validatore = ?, timestamp_validazione = ? WHERE id_relazione = ?"
                conn.execute(sql_upd, (admin_id, now, row["id_relazione"]))
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore validazione relazioni: {e}")
        return False
    finally:
        conn.close()

def salva_report_intervento(dati: Dict[str, Any]) -> bool:
    """Inserisce un report di intervento direttamente nella tabella definitiva."""
    cols = ", ".join(f'"{k}"' for k in dati.keys())
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(dati.values()))

def salva_relazione(dati: Dict[str, Any]) -> bool:
    """Inserisce una nuova relazione di reperibilità nel database."""
    cols = ", ".join(f'"{k}"' for k in dati.keys())
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO relazioni ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(dati.values()))

def get_validated_reports(table_name: str) -> pd.DataFrame:
    """Carica i dati storici validati da una tabella specifica."""
    if table_name not in ["relazioni", "report_interventi"]:
        return pd.DataFrame()
    conn = get_db_connection()
    try:
        return pd.read_sql_query(
            f"SELECT * FROM {table_name} WHERE stato = 'Validata' OR timestamp_validazione IS NOT NULL",
            conn,
        )
    finally:
        conn.close()

def get_validated_intervention_reports(
    matricola_tecnico: Optional[str] = None,
) -> pd.DataFrame:
    """Carica i report di intervento validati, opzionalmente filtrati per tecnico."""
    conn = get_db_connection()
    try:
        if matricola_tecnico:
            query = "SELECT * FROM report_interventi WHERE matricola_tecnico = ? ORDER BY data_riferimento_attivita DESC"
            return pd.read_sql_query(query, conn, params=(matricola_tecnico,))
        else:
            query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
            return pd.read_sql_query(query, conn)
    finally:
        conn.close()

def get_report_by_id(report_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """Recupera un singolo report per ID da una tabella specifica."""
    if table_name not in ["report_da_validare", "report_interventi"]:
        return None
    query = f"SELECT * FROM {table_name} WHERE id_report = ?"
    return DatabaseEngine.fetch_one(query, (report_id,))

def delete_report_by_id(report_id: str, table_name: str) -> bool:
    """Cancella un singolo report da una tabella specifica per ID."""
    if table_name not in ["report_da_validare", "report_interventi"]:
        return False
    sql = f"DELETE FROM {table_name} WHERE id_report = ?"
    return DatabaseEngine.execute(sql, (report_id,))

def insert_report(report_data: Dict[str, Any], table_name: str) -> bool:
    """Inserisce i dati di un report in una tabella specifica."""
    if table_name not in ["report_da_validare", "report_interventi"]:
        return False
    cols = ", ".join(f'"{k}"' for k in report_data.keys())
    placeholders = ", ".join("?" for _ in report_data)
    sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(report_data.values()))

def move_report_atomically(report_id: str, source_table: str, dest_table: str) -> bool:
    """Sposta un report tra tabelle in modo atomico tramite transazione."""
    report = get_report_by_id(report_id, source_table)
    if not report:
        return False
    conn = get_db_connection()
    try:
        with conn:
            cols = ", ".join(f'"{k}"' for k in report.keys())
            placeholders = ", ".join("?" for _ in report)
            sql_ins = f"INSERT INTO {dest_table} ({cols}) VALUES ({placeholders})"
            conn.execute(sql_ins, tuple(report.values()))
            conn.execute(
                f"DELETE FROM {source_table} WHERE id_report = ?", (report_id,)
            )
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore spostamento atomico report {report_id}: {e}")
        return False
    finally:
        conn.close()

def get_unvalidated_reports_by_technician(matricola: str) -> pd.DataFrame:
    """Recupera i report in attesa di validazione per un tecnico specifico."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_da_validare WHERE matricola_tecnico = ?"
        return pd.read_sql_query(query, conn, params=(matricola,))
    finally:
        conn.close()