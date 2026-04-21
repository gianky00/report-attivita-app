"""
Motore di astrazione per il database SQLite.
Fornisce metodi sicuri per l'esecuzione di query e gestione transazioni.
"""

import functools
import sqlite3
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from constants import DB_NAME
from core.logging import get_logger, measure_time

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def retry_on_lock(
    retries: int = 5, delay: float = 0.5
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decoratore per riprovare un'operazione se il database è bloccato."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_err = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower():
                        last_err = e
                        logger.warning(f"Database bloccato, tentativo {i + 1}/{retries}...")
                        time.sleep(delay * (i + 1))
                        continue
                    raise
            logger.error(f"Database bloccato dopo {retries} tentativi.")
            if last_err:
                raise last_err
            raise sqlite3.OperationalError("Database bloccato.")

        return wrapper

    return decorator


class DatabaseEngine:
    """Gestore centralizzato delle operazioni sul database."""

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """Restituisce una connessione configurata con row_factory e performance PRAGMAs."""
        conn = sqlite3.connect(DB_NAME, timeout=20)
        conn.row_factory = sqlite3.Row
        # Ottimizzazioni per performance e concorrenza
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @classmethod
    @retry_on_lock()
    @measure_time
    def execute(cls, query: str, params: tuple[Any, ...] = ()) -> bool:
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
    def fetch_all(cls, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Esegue una query SELECT e restituisce tutti i risultati."""
        conn = cls.get_connection()
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            if not rows:
                return []
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Errore fetch_all: {e} | Query: {query}")
            return []
        finally:
            conn.close()

    @classmethod
    @measure_time
    def fetch_one(cls, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Esegue una query SELECT e restituisce il primo risultato."""
        conn = cls.get_connection()
        try:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        except sqlite3.Error as e:
            logger.error(f"Errore fetch_one: {e} | Query: {query}")
            return None
        finally:
            conn.close()

    @classmethod
    @measure_time
    def insert_returning_id(cls, query: str, params: tuple[Any, ...] = ()) -> int | None:
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
