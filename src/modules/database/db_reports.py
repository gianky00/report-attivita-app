"""
Funzioni database per la gestione di report attività e relazioni di reperibilità.
Gestisce il flusso di validazione e la persistenza dei report finali.
"""

import datetime
import sqlite3
import uuid
from typing import Any

import pandas as pd

from constants import VALID_HISTORY_TABLES, VALID_REPORT_TABLES
from core.database import DatabaseEngine
from core.logging import get_logger, measure_time

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


def delete_reports_by_ids(report_ids: list[str]) -> bool:
    """Elimina definitivamente un set di report dalla coda di validazione."""
    if not report_ids:
        return True
    placeholders = ", ".join("?" for _ in report_ids)
    sql = f"DELETE FROM report_da_validare WHERE id_report IN ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(report_ids))


def process_and_commit_validated_reports(reports: list[dict[str, Any]]) -> bool:
    """Sposta i report validati dalla coda alla tabella definitiva in modo transazionale."""
    conn = get_db_connection()
    now = datetime.datetime.now().isoformat()
    try:
        with conn:
            for r in reports:
                r["timestamp_validazione"] = now
                cols = ", ".join(f'"{k}"' for k in r)
                placeholders = ", ".join("?" for _ in r)
                sql_ins = f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"  # nosec B608
                conn.execute(sql_ins, tuple(r.values()))
                conn.execute(
                    "DELETE FROM report_da_validare WHERE id_report = ?",
                    (r["id_report"],),
                )

                # --- AGGIUNTA NOTIFICA PER IL TECNICO ---
                pdl = r.get("pdl", "N/D")
                data_rif_raw = r.get("data_riferimento_attivita", "")
                try:
                    data_rif = datetime.datetime.fromisoformat(data_rif_raw).strftime("%d/%m/%Y")
                except Exception:
                    data_rif = data_rif_raw

                notifica = {
                    "ID_Notifica": str(uuid.uuid4()),
                    "Timestamp": now,
                    "Destinatario_Matricola": r.get("matricola_tecnico"),
                    "Messaggio": f"✅ Il tuo report per il PdL {pdl} del {data_rif} è stato validato.",
                    "Stato": "non letta",
                    "Link_Azione": "/?tab=Storico",  # Porta l'utente allo storico per vedere il report validato
                }
                cols_n = ", ".join(f'"{k}"' for k in notifica)
                placeholders_n = ", ".join("?" for _ in notifica)
                conn.execute(
                    f"INSERT INTO notifiche ({cols_n}) VALUES ({placeholders_n})",  # nosec B608
                    tuple(notifica.values()),
                )

                # --- AGGIORNAMENTO STATO PDL_PROGRAMMAZIONE ---
                sql_pdl = (
                    'UPDATE "pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot" SET stato = \'VALIDATO\', '
                    "timestamp_validazione = ? WHERE pdl = ? AND data_intervento = ?"
                )
                conn.execute(sql_pdl, (now, pdl, r.get("data_riferimento_attivita")))

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
        return pd.read_sql_query("SELECT * FROM relazioni WHERE stato = 'Inviata'", conn)
    finally:
        conn.close()


def process_and_commit_validated_relazioni(df: pd.DataFrame, admin_id: str) -> bool:
    """Aggiorna lo stato delle relazioni validate memorizzando il validatore."""
    conn = get_db_connection()
    now = datetime.datetime.now().isoformat()
    try:
        with conn:
            for _, row in df.iterrows():
                sql_upd = (
                    "UPDATE relazioni SET stato = 'Validata', id_validatore = ?, "
                    "timestamp_validazione = ? WHERE id_relazione = ?"
                )
                conn.execute(sql_upd, (admin_id, now, row["id_relazione"]))
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore validazione relazioni: {e}")
        return False
    finally:
        conn.close()


def salva_report_intervento(dati: dict[str, Any]) -> bool:
    """Inserisce un report di intervento direttamente nella tabella definitiva."""
    cols = ", ".join(f'"{k}"' for k in dati)
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(dati.values()))


def salva_relazione(dati: dict[str, Any]) -> bool:
    """Inserisce una nuova relazione di reperibilità nel database."""
    cols = ", ".join(f'"{k}"' for k in dati)
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO relazioni ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(dati.values()))


def get_validated_reports(table_name: str) -> pd.DataFrame:
    """Carica i dati storici validati da una tabella specifica."""
    if table_name not in VALID_HISTORY_TABLES:
        logger.warning(f"Tentativo di accesso a tabella non valida: {table_name}")
        return pd.DataFrame()
    conn = get_db_connection()
    try:
        sql = (
            f"SELECT * FROM {table_name} WHERE stato = 'Validata' "  # nosec B608
            "OR timestamp_validazione IS NOT NULL"
        )
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def get_validated_intervention_reports(
    matricola_tecnico: str | None = None,
) -> pd.DataFrame:
    """Carica i report di intervento validati, opzionalmente filtrati per tecnico."""
    conn = get_db_connection()
    try:
        if matricola_tecnico:
            query = (
                "SELECT * FROM report_interventi WHERE matricola_tecnico = ? "
                "ORDER BY data_riferimento_attivita DESC"
            )
            return pd.read_sql_query(query, conn, params=(matricola_tecnico,))

        query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def get_report_by_id(report_id: str, table_name: str) -> dict[str, Any] | None:
    """Recupera un singolo report per ID da una tabella specifica."""
    if table_name not in VALID_REPORT_TABLES:
        return None
    query = f"SELECT * FROM {table_name} WHERE id_report = ?"  # nosec B608
    return DatabaseEngine.fetch_one(query, (report_id,))


def delete_report_by_id(report_id: str, table_name: str) -> bool:
    """Cancella un singolo report da una tabella specifica per ID."""
    if table_name not in VALID_REPORT_TABLES:
        return False
    sql = f"DELETE FROM {table_name} WHERE id_report = ?"  # nosec B608
    return DatabaseEngine.execute(sql, (report_id,))


def insert_report(report_data: dict[str, Any], table_name: str) -> bool:
    """Inserisce i dati di un report in una tabella specifica."""
    if table_name not in VALID_REPORT_TABLES:
        return False
    
    conn = get_db_connection()
    now = datetime.datetime.now().isoformat()
    try:
        with conn:
            cols = ", ".join(f'"{k}"' for k in report_data)
            placeholders = ", ".join("?" for _ in report_data)
            sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"  # nosec B608
            conn.execute(sql, tuple(report_data.values()))

            # Se stiamo inserendo nella coda di validazione, aggiorniamo pdl_programmazione
            if table_name == "report_da_validare":
                pdl = report_data.get("pdl")
                data_rif = report_data.get("data_riferimento_attivita")
                if pdl and data_rif:
                    sql_pdl = (
                        'UPDATE "pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot" SET stato = \'INVIATO\', '
                        "timestamp_invio_report = ? WHERE pdl = ? AND data_intervento = ?"
                    )
                    conn.execute(sql_pdl, (now, pdl, data_rif))
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore inserimento report in {table_name}: {e}")
        return False
    finally:
        conn.close()


def move_report_atomically(report_id: str, source_table: str, dest_table: str) -> bool:
    """Sposta un report tra tabelle in modo atomico tramite transazione."""
    if source_table not in VALID_REPORT_TABLES or dest_table not in VALID_REPORT_TABLES:
        return False

    report = get_report_by_id(report_id, source_table)
    if not report:
        return False

    conn = get_db_connection()
    try:
        with conn:
            cols = ", ".join(f'"{k}"' for k in report)
            placeholders = ", ".join("?" for _ in report)
            sql_ins = f"INSERT INTO {dest_table} ({cols}) VALUES ({placeholders})"  # nosec B608
            conn.execute(sql_ins, tuple(report.values()))
            sql_del = f"DELETE FROM {source_table} WHERE id_report = ?"  # nosec B608
            conn.execute(sql_del, (report_id,))
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


def annulla_invio_report(report_id: str, matricola: str) -> bool:
    """Cancella un report dalla coda di validazione se appartiene al tecnico specificato."""
    sql = "DELETE FROM report_da_validare WHERE id_report = ? AND matricola_tecnico = ?"
    return DatabaseEngine.execute(sql, (report_id, matricola))
