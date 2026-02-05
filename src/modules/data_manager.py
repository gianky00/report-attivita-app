"""
Modulo per la gestione e il caricamento dei dati delle attività (Facade).
Riesporta le funzioni dai moduli specializzati per mantenere la compatibilità.
"""

from modules.importers.excel_giornaliera import (
    get_all_assigned_activities,
    trova_attivita,
)
from modules.knowledge_base import carica_knowledge_core
from modules.reports_manager import scrivi_o_aggiorna_risposta

__all__ = [
    "carica_knowledge_core",
    "scrivi_o_aggiorna_risposta",
    "trova_attivita",
    "get_all_assigned_activities",
]
