"""
Funzioni database per la gestione utenti e log di accesso.
Gestisce l'anagrafica tecnica, la cronologia login e le richieste di sostituzione.
"""

import sqlite3
from typing import Any

import pandas as pd
from core.database import DatabaseEngine
from core.logging import measure_time


def get_db_connection() -> sqlite3.Connection:
    """Restituisce una connessione al database core."""
    return DatabaseEngine.get_connection()


@measure_time
def get_all_users() -> pd.DataFrame:
    """Carica l'intero elenco utenti registrati nel sistema."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM contatti", conn)
    finally:
        conn.close()


def get_last_login(matricola: str) -> str | None:
    """Recupera il timestamp dell'ultimo accesso andato a buon fine per l'utente."""
    query = """
        SELECT timestamp
        FROM access_logs
        WHERE username = ? AND (status = 'Login 2FA riuscito'
        OR status = 'Setup 2FA completato e login riuscito')
        ORDER BY timestamp DESC
        LIMIT 1
    """
    res = DatabaseEngine.fetch_one(query, (matricola,))
    return res["timestamp"] if res else None


@measure_time
def get_access_logs() -> pd.DataFrame:
    """Recupera la cronologia integrale dei tentativi di accesso."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM access_logs", conn)
    finally:
        conn.close()


def get_substitution_request_by_id(id_richiesta: str) -> dict[str, Any] | None:
    """Recupera i dettagli di una richiesta di cambio turno tramite ID."""
    query = "SELECT * FROM sostituzioni WHERE ID_Richiesta = ?"
    return DatabaseEngine.fetch_one(query, (id_richiesta,))


def delete_substitution_request(id_richiesta: str) -> bool:
    """Rimuove una richiesta di sostituzione dal database."""
    sql = "DELETE FROM sostituzioni WHERE ID_Richiesta = ?"
    return DatabaseEngine.execute(sql, (id_richiesta,))


def add_substitution_request(data: dict[str, Any]) -> bool:
    """Inserisce una nuova proposta di scambio turno nel database."""
    cols = ", ".join(f'"{k}"' for k in data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT INTO sostituzioni ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(data.values()))


@measure_time
def get_all_substitutions() -> pd.DataFrame:
    """Carica tutte le richieste di sostituzione pendenti."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM sostituzioni", conn)
    finally:
        conn.close()
