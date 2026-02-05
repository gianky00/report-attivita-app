"""
Funzioni database per la gestione di richieste materiali e assenze.
Include lo storico delle approvazioni e il monitoraggio delle richieste pendenti.
"""

import sqlite3
from typing import Any

import pandas as pd
from core.database import DatabaseEngine
from core.logging import measure_time


def get_db_connection() -> sqlite3.Connection:
    """Restituisce una connessione al database core."""
    return DatabaseEngine.get_connection()


def add_material_request(request_data: dict[str, Any]) -> bool:
    """Inserisce una nuova richiesta di materiali nel database."""
    cols = ", ".join(f'"{k}"' for k in request_data.keys())
    placeholders = ", ".join("?" for _ in request_data)
    sql = f"INSERT INTO richieste_materiali ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(request_data.values()))


def add_leave_request(request_data: dict[str, Any]) -> bool:
    """Inserisce una nuova richiesta di assenza nel database."""
    cols = ", ".join(f'"{k}"' for k in request_data.keys())
    placeholders = ", ".join("?" for _ in request_data)
    sql = f"INSERT INTO richieste_assenze ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(request_data.values()))


@measure_time
def get_material_requests() -> pd.DataFrame:
    """Recupera l'elenco di tutte le richieste materiali correnti."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM richieste_materiali", conn)
    finally:
        conn.close()


@measure_time
def get_leave_requests() -> pd.DataFrame:
    """Recupera l'elenco di tutte le richieste di assenza correnti."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM richieste_assenze", conn)
    finally:
        conn.close()


def salva_storico_materiali(dati: dict[str, Any]) -> bool:
    """Archivia una richiesta materiali nello storico dopo l'approvazione/rifiuto."""
    cols = ", ".join(f'"{k}"' for k in dati.keys())
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO storico_richieste_materiali ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(dati.values()))


def salva_storico_assenze(dati: dict[str, Any]) -> bool:
    """Archivia una richiesta assenza nello storico dopo l'approvazione/rifiuto."""
    cols = ", ".join(f'"{k}"' for k in dati.keys())
    placeholders = ", ".join("?" for _ in dati)
    sql = f"INSERT INTO storico_richieste_assenze ({cols}) VALUES ({placeholders})"  # nosec B608
    return DatabaseEngine.execute(sql, tuple(dati.values()))


@measure_time
def get_storico_richieste_materiali() -> pd.DataFrame:
    """Recupera l'intero storico delle richieste materiali archiviate."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM storico_richieste_materiali", conn)
    finally:
        conn.close()


@measure_time
def get_storico_richieste_assenze() -> pd.DataFrame:
    """Recupera l'intero storico delle richieste assenze archiviate."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM storico_richieste_assenze", conn)
    finally:
        conn.close()
