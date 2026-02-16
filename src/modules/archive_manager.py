"""
Logica per la gestione dell'archivio storico delle schede di manutenzione.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path(__file__).parent.parent.parent / "schedario.db"

def search_archive(query: str, limit: int = 50) -> pd.DataFrame:
    """Cerca file nell'archivio per nome (case-insensitive)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # LOWER() rende la ricerca insensibile alle maiuscole/minuscole
        sql = """
            SELECT filename, year, month, last_modified, full_path 
            FROM maintenance_archive 
            WHERE LOWER(filename) LIKE LOWER(?) 
            ORDER BY year DESC, month DESC, filename ASC 
            LIMIT ?
        """
        df = pd.read_sql_query(sql, conn, params=(f"%{query}%", limit))
        return df
    finally:
        conn.close()

def get_archive_stats() -> Dict[str, Any]:
    """Ritorna statistiche rapide sull'archivio."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), MIN(year), MAX(year) FROM maintenance_archive")
        count, min_y, max_y = cursor.fetchone()
        return {
            "total_files": count,
            "year_range": f"{min_y} - {max_y}" if min_y else "N/A"
        }
    finally:
        conn.close()
