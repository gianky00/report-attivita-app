"""
Sistema di logging strutturato enterprise per l'applicazione.
Supporta output JSON, tracciamento performance e propagazione del contesto.
"""

import functools
import json
import logging
import sys
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

# --- CONFIGURAZIONE ---
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.json"
LOG_DIR.mkdir(exist_ok=True)

# Contesto globale thread-local per trace_id e metadati aggiuntivi
_context = threading.local()

P = ParamSpec("P")
R = TypeVar("R")


class JsonFormatter(logging.Formatter):
    """Formatter personalizzato per produrre log in formato JSON con sanitizzazione PII."""

    SENSITIVE_KEYS = {"password", "secret", "2fa_secret", "passwordhash", "token"}

    def _sanitize(self, data: Any) -> Any:
        """Maschera i valori sensibili in un dizionario o lista."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if isinstance(k, str) and any(
                    s in k.lower() for s in self.SENSITIVE_KEYS
                ):
                    sanitized[k] = "********"
                elif isinstance(v, (dict, list)):
                    sanitized[k] = self._sanitize(v)
                else:
                    sanitized[k] = v
            return sanitized
        if isinstance(data, list):
            return [self._sanitize(item) for item in data]
        return data

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        # Sanitizza il messaggio principale se contiene parole chiave
        msg_str = str(log_data["message"]).lower()
        if "password" in msg_str or "secret" in msg_str:
            log_data["message"] = (
                "[REDACTED] Messaggio contenente dati potenzialmente sensibili"
            )

        # Aggiungi trace_id se presente nel contesto
        if hasattr(_context, "trace_id"):
            log_data["trace_id"] = _context.trace_id

        # Aggiungi metadati extra dal contesto (sanitizzati)
        if hasattr(_context, "extra") and isinstance(_context.extra, dict):
            log_data.update(self._sanitize(_context.extra))

        # Aggiungi attributi extra passati direttamente nella chiamata log (sanitizzati)
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(self._sanitize(record.extra_data))

        # Gestione eccezioni
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Restituisce un logger configurato per il logging strutturato.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JsonFormatter())
        logger.addHandler(console_handler)

        # File Handler
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    return logger


@contextmanager
def with_context(trace_id: str | None = None, **kwargs):
    """
    Manager di contesto per iniettare trace_id e metadati nei log.
    """
    old_trace_id = getattr(_context, "trace_id", None)
    old_extra = getattr(_context, "extra", {}).copy()

    _context.trace_id = trace_id or old_trace_id or str(uuid.uuid4())
    if not hasattr(_context, "extra"):
        _context.extra = {}
    _context.extra.update(kwargs)

    try:
        yield _context.trace_id
    finally:
        _context.trace_id = old_trace_id
        _context.extra = old_extra


def measure_time(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decoratore per misurare il tempo di esecuzione di una funzione e loggarlo.
    """
    logger = get_logger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start_time
            logger.info(
                f"Esecuzione completata: {func.__name__}",
                extra={
                    "extra_data": {
                        "duration_sec": round(duration, 4),
                        "status": "success",
                    }
                },
            )
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                f"Errore durante l'esecuzione di {func.__name__}: {e}",
                extra={
                    "extra_data": {
                        "duration_sec": round(duration, 4),
                        "status": "error",
                    }
                },
                exc_info=True,
            )
            raise

    return wrapper