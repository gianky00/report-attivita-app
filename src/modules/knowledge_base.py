"""
Logica per il caricamento del Knowledge Core JSON.
"""

import json
from pathlib import Path
from typing import Any

import streamlit as st

import config


@st.cache_data
def carica_knowledge_core() -> dict[str, Any] | None:
    """Carica il file JSON del Knowledge Core dalla root del progetto."""
    path = Path(getattr(config, "PATH_KNOWLEDGE_CORE", "knowledge_core.json"))
    try:
        if not path.exists():
            st.error(f"Errore critico: File '{path}' non trovato.")
            return None
        result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return result
    except json.JSONDecodeError:
        st.error(f"Errore critico: Il file '{path}' non è un JSON valido.")
        return None
