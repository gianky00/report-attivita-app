"""
Logica per il caricamento del Knowledge Core JSON.
"""
import json
from pathlib import Path

import streamlit as st

import config


@st.cache_data
def carica_knowledge_core() -> dict | None:
    """Carica il file JSON del Knowledge Core dalla root del progetto."""
    path = Path(config.PATH_KNOWLEDGE_CORE)
    try:
        if not path.exists():
            st.error(f"Errore critico: File '{path}' non trovato.")
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        st.error(f"Errore critico: Il file '{path}' non è un JSON valido.")
        return None
