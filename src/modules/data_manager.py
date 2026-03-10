"""
Modulo per la gestione e il caricamento dei dati delle attività (Facade).
Riesporta le funzioni dai moduli specializzati per mantenere la compatibilità.
"""

from core.logging import get_logger
from modules.importers.excel_giornaliera import (
    get_all_assigned_activities,
    trova_attivita,
)
from modules.knowledge_base import carica_knowledge_core
from modules.reports_manager import scrivi_o_aggiorna_risposta

logger = get_logger(__name__)


def trigger_smart_sync() -> bool:
    """
    Funzione deprecata. La sincronizzazione ora è gestita
    da uno scheduler esterno al livello di sistema operativo
    per evitare problemi di caching dei volumi Docker.
    """
    return True


__all__ = [
    "carica_knowledge_core",
    "get_all_assigned_activities",
    "scrivi_o_aggiorna_risposta",
    "trigger_smart_sync",
    "trova_attivita",
]
