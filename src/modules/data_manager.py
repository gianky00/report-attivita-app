"""
Modulo per la gestione e il caricamento dei dati delle attività (Facade).
Riesporta le funzioni dai moduli specializzati per mantenere la compatibilità.
"""

import datetime
import subprocess
import sys
from pathlib import Path

from modules.importers.excel_giornaliera import (
    get_all_assigned_activities,
    trova_attivita,
)
from modules.knowledge_base import carica_knowledge_core
from modules.reports_manager import scrivi_o_aggiorna_risposta
from core.logging import get_logger

logger = get_logger(__name__)


def trigger_smart_sync() -> bool:
    """
    Esegue la sincronizzazione solo se necessario (file remoto più recente o tempo trascorso).
    Usa un subprocess per non bloccare l'interfaccia principale se possibile.
    """
    import streamlit as st
    
    # Previene esecuzioni troppo frequenti (ogni 5 minuti)
    last_sync = st.session_state.get("last_smart_sync_time")
    now = datetime.datetime.now()
    
    if last_sync and (now - last_sync).total_seconds() < 300:
        return False
        
    try:
        # Percorso dello script di sincronizzazione
        sync_script = Path(__file__).parent.parent.parent / "scripts" / "sync_data.py"
        
        # Esegue la sincronizzazione in background
        subprocess.Popen([sys.executable, str(sync_script)], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        
        st.session_state.last_smart_sync_time = now
        logger.info("Trigger Sincronizzazione Intelligente inviato.")
        return True
    except Exception as e:
        logger.error(f"Errore durante il trigger della sincronizzazione: {e}")
        return False


__all__ = [
    "carica_knowledge_core",
    "get_all_assigned_activities",
    "scrivi_o_aggiorna_risposta",
    "trova_attivita",
    "trigger_smart_sync",
]
