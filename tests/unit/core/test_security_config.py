"""
Test per sicurezza API e fallback di configurazione.
"""

import streamlit as st
import pytest
from modules.ai_engine import revisiona_con_ia
from config import validate_config

def test_ai_revision_no_key(mocker):
    """Verifica il graceful failure senza API Key."""
    mocker.patch("streamlit.secrets", {}) 
    res = revisiona_con_ia("test")
    assert res["success"] is False
    assert any(term in res["error"] for term in ["incompleta", "non disponibile"])

def test_config_defaults(mocker):
    """Verifica che validate_config non esca se le chiavi sono presenti."""
    # Mockiamo tutte le chiavi obbligatorie per evitare sys.exit
    full_conf = {
        "general": {"app_name": "Test"},
        "path_storico_db": "test.db",
        "path_gestionale": "test.db",
        "path_giornaliera_base": ".",
        "path_attivita_programmate": "test.xlsx"
    }
    mocker.patch("streamlit.secrets", full_conf)
    # Non deve sollevare SystemExit
    validate_config(full_conf)
    assert True