"""
Motore di astrazione per il database SQLite.
Fornisce metodi sicuri per l'esecuzione di query e gestione transazioni.
"""

import functools
import sqlite3
import time
from collections.abc import Callable
from typing import Any

from src.core.logging import get_logger, measure_time

logger = get_logger(__name__)
DB_NAME = "schedario.db"

def retry_on_lock(retries: int = 5, delay: float = 0.5):
    """Decoratore per riprovare un'operazione se il database è bloccato."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower():
                        last_err = e
                        logger.warning(
                            f"Database bloccato, tentativo {i+1}/{retries}..."
                        )
                        time.sleep(delay * (i + 1))
                        continue
                    raise
            logger.error(f"Database bloccato dopo {retries} tentativi.")
            raise last_err
        return wrapper
    return decorator

class DatabaseEngine:
    """Gestore centralizzato delle operazioni sul database."""

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """Restituisce una connessione configurata con row_factory."""
        conn = sqlite3.connect(DB_NAME, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    @retry_on_lock()
    @measure_time
    def execute(cls, query: str, params: tuple = ()) -> bool:
        """Esegue una query di modifica (INSERT, UPDATE, DELETE)."""
        conn = cls.get_connection()
        try:
            with conn:
                cursor = conn.execute(query, params)
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Errore esecuzione query: {e} | Query: {query}")
            return False
        finally:
            conn.close()

    @classmethod
    @measure_time
    def fetch_all(cls, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Esegue una query SELECT e restituisce tutti i risultati."""
        conn = cls.get_connection()
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            if not rows: return []
            # Prova a usare keys() di sqlite3.Row, altrimenti fallback a dict vuoto
            try:
                return [{k: row[k] for k in row.keys()} for row in rows]
            except AttributeError:
                return [dict(row) if hasattr(row, "__iter__") and not isinstance(row, tuple) else {} for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Errore fetch_all: {e} | Query: {query}")
            return []
        finally:
            conn.close()

    @classmethod
    @measure_time
    def fetch_one(cls, query: str, params: tuple = ()) -> dict[str, Any] | None:
        """Esegue una query SELECT e restituisce il primo risultato."""
        conn = cls.get_connection()
        try:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if not row: return None
            try:
                return {k: row[k] for k in row.keys()}
            except AttributeError:
                # Se row è una tupla e non Row, non possiamo mappare le chiavi senza cursore
                return dict(row) if hasattr(row, "__iter__") and not isinstance(row, tuple) else None
        except sqlite3.Error as e:
            logger.error(f"Errore fetch_one: {e} | Query: {query}")
            return None
        finally:
            conn.close()

    @classmethod
    @measure_time
    def insert_returning_id(cls, query: str, params: tuple = ()) -> int | None:
        """Esegue un INSERT e restituisce l'ID inserito."""
        conn = cls.get_connection()
        try:
            with conn:
                cursor = conn.execute(query, params)
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Errore inserimento: {e} | Query: {query}")
            return None
        finally:
            conn.close()
