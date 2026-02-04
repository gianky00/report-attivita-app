"""
Funzioni database per la gestione di turni, prenotazioni e bacheca scambi.
Gestisce l'allocazione del personale e la cronologia delle modifiche ai turni.
"""
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
def get_shifts_by_type(shift_type: str) -> pd.DataFrame:
    """Carica i turni filtrati per tipologia (es. Assistenza, Reperibilità)."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM turni WHERE Tipo = ? ORDER BY Data DESC"
        return pd.read_sql_query(query, conn, params=(shift_type,))
    except sqlite3.Error as e:
        logger.error(f"Errore nel caricare i turni per tipo '{shift_type}': {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def create_shift(data: Dict[str, Any]) -> bool:
    """Crea un nuovo turno operativo nel sistema."""
    cols = ", ".join(f'"{k}"' for k in data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT INTO turni ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(data.values()))

def update_shift(shift_id: str, update_data: Dict[str, Any]) -> bool:
    """Aggiorna i parametri di un turno esistente (data, orari, descrizione)."""
    set_clause = ", ".join(f'"{k}" = ?' for k in update_data.keys())
    sql = f"UPDATE turni SET {set_clause} WHERE ID_Turno = ?"
    params = list(update_data.values()) + [shift_id]
    return DatabaseEngine.execute(sql, tuple(params))

def get_shift_by_id(shift_id: str) -> Optional[Dict[str, Any]]:
    """Recupera i dati completi di un singolo turno tramite ID."""
    query = "SELECT * FROM turni WHERE ID_Turno = ?"
    return DatabaseEngine.fetch_one(query, (shift_id,))

def add_shift_log(log_data: Dict[str, Any]) -> bool:
    """Registra una transazione di modifica turno nello storico log."""
    cols = ", ".join(f'"{k}"' for k in log_data.keys())
    placeholders = ", ".join("?" for _ in log_data)
    sql = f"INSERT INTO shift_logs ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(log_data.values()))

def get_bookings_for_shift(shift_id: str) -> pd.DataFrame:
    """Recupera tutte le prenotazioni del personale associate a un turno."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM prenotazioni WHERE ID_Turno = ?"
        return pd.read_sql_query(query, conn, params=(shift_id,))
    finally:
        conn.close()

def add_booking(data: Dict[str, Any]) -> bool:
    """Inserisce una nuova prenotazione tecnico/aiutante per un turno."""
    cols = ", ".join(f'"{k}"' for k in data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT INTO prenotazioni ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(data.values()))

def delete_booking(booking_id: str, shift_id: str) -> bool:
    """Elimina una specifica prenotazione da un turno."""
    sql = "DELETE FROM prenotazioni WHERE ID_Prenotazione = ? AND ID_Turno = ?"
    return DatabaseEngine.execute(sql, (booking_id, shift_id))

def delete_bookings_for_shift(shift_id: str) -> bool:
    """Rimuove integralmente tutto il personale assegnato a un turno."""
    sql = "DELETE FROM prenotazioni WHERE ID_Turno = ?"
    return DatabaseEngine.execute(sql, (shift_id,))

def get_booking_by_user_and_shift(matricola: str, turno_id: str) -> Optional[Dict[str, Any]]:
    """Cerca se un determinato utente è già prenotato per un turno specifico."""
    query = "SELECT * FROM prenotazioni WHERE Matricola = ? AND ID_Turno = ?"
    return DatabaseEngine.fetch_one(query, (matricola, turno_id))

def check_user_oncall_conflict(matricola: str, data_turno: str) -> bool:
    """Verifica se l'utente è già impegnato in reperibilità per la data indicata."""
    query = """
        SELECT COUNT(*) as count 
        FROM prenotazioni p
        JOIN turni t ON p.ID_Turno = t.ID_Turno
        WHERE p.Matricola = ? AND t.Data = ? AND t.Tipo = 'Reperibilità'
    """
    res = DatabaseEngine.fetch_one(query, (matricola, data_turno))
    return bool(res and res["count"] > 0)

def update_booking_user(turno_id: str, vecchia_mat: str, nuova_mat: str) -> bool:
    """Effettua il subentro di un utente in una prenotazione esistente (scambio)."""
    sql = "UPDATE prenotazioni SET Matricola = ? WHERE ID_Turno = ? AND Matricola = ?"
    return DatabaseEngine.execute(sql, (nuova_mat, turno_id, vecchia_mat))

@measure_time
def get_all_bookings() -> pd.DataFrame:
    """Carica l'elenco completo di tutte le prenotazioni attive nel sistema."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM prenotazioni", conn)
    finally:
        conn.close()

def get_bacheca_item_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    """Recupera un annuncio della bacheca tramite il suo ID."""
    query = "SELECT * FROM bacheca WHERE ID_Bacheca = ?"
    return DatabaseEngine.fetch_one(query, (item_id,))

def update_bacheca_item(item_id: str, update_data: Dict[str, Any]) -> bool:
    """Aggiorna lo stato o i dettagli di un annuncio in bacheca."""
    set_clause = ", ".join(f'"{k}" = ?' for k in update_data.keys())
    sql = f"UPDATE bacheca SET {set_clause} WHERE ID_Bacheca = ?"
    params = list(update_data.values()) + [item_id]
    return DatabaseEngine.execute(sql, tuple(params))

def add_bacheca_item(item_data: Dict[str, Any]) -> bool:
    """Inserisce un nuovo annuncio di turno disponibile nella bacheca scambi."""
    cols = ", ".join(f'"{k}"' for k in item_data.keys())
    placeholders = ", ".join("?" for _ in item_data)
    sql = f"INSERT INTO bacheca ({cols}) VALUES ({placeholders})"
    return DatabaseEngine.execute(sql, tuple(item_data.values()))

@measure_time
def get_all_bacheca_items() -> pd.DataFrame:
    """Recupera tutti gli annunci presenti in bacheca, inclusi quelli già assegnati."""
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM bacheca", conn)
    finally:
        conn.close()