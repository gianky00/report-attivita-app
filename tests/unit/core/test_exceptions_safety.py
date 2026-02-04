"""
Test per il decoratore safe_streamlit_run.
"""

import pytest
from unittest.mock import MagicMock, patch
import streamlit as st
from src.core.exceptions import safe_streamlit_run

def test_safe_streamlit_run_catches_exception(mocker):
    """Verifica che le eccezioni siano catturate e mostrate in UI."""
    # Mock di streamlit
    mock_error = mocker.patch("streamlit.error")
    mock_stop = mocker.patch("streamlit.stop")
    mock_markdown = mocker.patch("streamlit.markdown")
    mock_checkbox = mocker.patch("streamlit.checkbox", return_value=False)
    
    @safe_streamlit_run
    def crashing_func():
        raise ValueError("Boom!")
    
    crashing_func()
    
    # Verifiche
    assert mock_error.called
    assert mock_markdown.called
    assert mock_stop.called
    # Controlla che il log sia stato chiamato (opzionale se vogliamo essere profondi)
    # logger.critical è mockato implicitamente dal sistema di test se non patchato, 
    # ma verifichiamo la UI che è l'effetto desiderato.

def test_safe_streamlit_run_passes_return_value():
    """Verifica che il decoratore non alteri il valore di ritorno se non ci sono errori."""
    @safe_streamlit_run
    def healthy_func():
        return "Everything is fine"
    
    result = healthy_func()
    assert result == "Everything is fine"