"""
Funzioni database di sistema, notifiche e utility generiche.
Gestisce le esclusioni degli assegnamenti, le notifiche e le operazioni sulle tabelle.
"""
import datetime
import sqlite3
from typing import List, Dict, Any

import pandas as pd
from src.core.database import DatabaseEngine
from src.core.logging import get_logger

logger = get_logger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Restituisce una connessione al database core."""
    return DatabaseEngine.get_connection()

def add_assignment_exclusion(matricola_escludente: str, id_attivita: str) -> bool:
    """Registra un blocco per un determinato assegnamento di attività."""
    sql = (
        "INSERT INTO esclusioni_assegnamenti "
        "(matricola_escludente, id_attivita, timestamp) VALUES (?, ?, ?)"
    )
    params = (matricola_escludente, id_attivita, datetime.datetime.now().isoformat())
    return DatabaseEngine.execute(sql, params)

def get_globally_excluded_activities() -> List[str]:
    """Recupera l'elenco di tutti i PdL/Attività bloccati a livello globale."""
    query = "SELECT id_attivita FROM esclusioni_assegnamenti"
    rows = DatabaseEngine.fetch_all(query)
    return [row["id_attivita"] for row in rows]

def get_notifications_for_user(utente: str) -> List[Dict[str, Any]]:
    """Recupera la cronologia delle notifiche per un determinato utente."""
    query = "SELECT * FROM notifiche WHERE Destinatario_Matricola = ? ORDER BY Timestamp DESC"
    return DatabaseEngine.fetch_all(query, (utente,))

def add_notification(n: Dict[str, Any]) -> bool:
    """Salva una nuova notifica destinata a un tecnico o admin."""
    cols = ", ".join(f'"{k}"' for k in n.keys())
    placeholders = ", ".join("?" for _ in n)
    sql = f"INSERT INTO notifiche ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(n.values()))

def count_unread_notifications(matricola: str) -> int:
    """Restituisce il numero di notifiche pendenti (non lette) per l'utente."""
    query = "SELECT COUNT(*) as count FROM notifiche WHERE Destinatario_Matricola = ? AND Stato = 'non letta'"
    res = DatabaseEngine.fetch_one(query, (matricola,))
    return res["count"] if res else 0

def save_table_data(df: pd.DataFrame, table_name: str) -> bool:
    """Sincronizza integralmente una tabella del DB partendo da un DataFrame Pandas."""
    conn = get_db_connection()
    try:
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        return True
    except sqlite3.Error as e:
        logger.error(f"Errore sovrascrittura tabella {table_name}: {e}")
        return False
    finally:
        conn.close()

def get_table_data(table_name: str) -> pd.DataFrame:
    """Scarica il contenuto integrale di una tabella in un DataFrame."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()

def get_table_names() -> List[str]:
    """Interroga lo schema SQLite per ottenere l'elenco delle tabelle non di sistema."""
    query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    rows = DatabaseEngine.fetch_all(query)
    return [row["name"] for row in rows if not row["name"].startswith("sqlite_")]